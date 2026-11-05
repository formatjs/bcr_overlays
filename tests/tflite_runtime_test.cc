#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <vector>

#include "base/at_exit.h"
#include "base/command_line.h"
#include "base/task/thread_pool/thread_pool_instance.h"
#include "tensorflow/lite/builtin_ops.h"
#include "tensorflow/lite/delegates/xnnpack/xnnpack_delegate.h"
#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/interpreter_builder.h"
#include "tensorflow/lite/kernels/register.h"
#include "tensorflow/lite/model_builder.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/schema/schema_utils.h"
#include "tensorflow/lite/version.h"

#define CHECK_CASE(condition)                                      \
  do {                                                             \
    if (!(condition)) {                                            \
      std::fprintf(stderr, "line %d: %s\n", __LINE__, #condition); \
      return 1;                                                    \
    }                                                              \
  } while (false)

constexpr int kWidth = 1024;

flatbuffers::DetachedBuffer MakeModel(bool quantized) {
  tflite::ModelT model;
  model.version = TFLITE_SCHEMA_VERSION;
  model.buffers.push_back(std::make_unique<tflite::BufferT>());
  auto code = std::make_unique<tflite::OperatorCodeT>();
  code->builtin_code = tflite::BuiltinOperator_ADD;
  code->deprecated_builtin_code = tflite::BuiltinOperator_ADD;
  code->version = quantized ? 2 : 1;
  model.operator_codes.push_back(std::move(code));

  auto graph = std::make_unique<tflite::SubGraphT>();
  for (unsigned i = 0; i < 3; ++i) {
    auto tensor = std::make_unique<tflite::TensorT>();
    tensor->shape = {1, kWidth};
    tensor->shape_signature = {-1, kWidth};
    tensor->has_rank = true;
    tensor->type =
        quantized ? tflite::TensorType_INT8 : tflite::TensorType_FLOAT32;
    if (quantized) {
      tensor->quantization =
          std::make_unique<tflite::QuantizationParametersT>();
      tensor->quantization->scale = {i == 2 ? 0.25f : 0.5f};
      tensor->quantization->zero_point = {i == 2 ? 4 : -3};
    }
    graph->tensors.push_back(std::move(tensor));
  }
  graph->inputs = {0, 1};
  graph->outputs = {2};
  auto op = std::make_unique<tflite::OperatorT>();
  op->inputs = {0, 1};
  op->outputs = {2};
  op->builtin_options.Set(tflite::AddOptionsT{});
  graph->operators.push_back(std::move(op));
  model.subgraphs.push_back(std::move(graph));

  flatbuffers::FlatBufferBuilder builder;
  const auto packed = tflite::Model::Pack(builder, &model);
  tflite::FinishModelBuffer(builder, packed);
  return builder.Release();
}

int Infer(tflite::Interpreter& interpreter, bool quantized, int batches) {
  CHECK_CASE(interpreter.ResizeInputTensorStrict(0, {batches, kWidth}) ==
             kTfLiteOk);
  CHECK_CASE(interpreter.ResizeInputTensorStrict(1, {batches, kWidth}) ==
             kTfLiteOk);
  CHECK_CASE(interpreter.AllocateTensors() == kTfLiteOk);
  const int count = batches * kWidth;
  for (int i = 0; i < count; ++i) {
    if (quantized) {
      interpreter.typed_input_tensor<int8_t>(0)[i] = (i * 7) % 61 - 30;
      interpreter.typed_input_tensor<int8_t>(1)[i] = (i * 11) % 67 - 33;
    } else {
      interpreter.typed_input_tensor<float>(0)[i] = ((i * 7) % 61 - 30) * 0.25f;
      interpreter.typed_input_tensor<float>(1)[i] = ((i * 11) % 67 - 33) * 0.5f;
    }
  }
  CHECK_CASE(interpreter.Invoke() == kTfLiteOk);
  const TfLiteTensor* output = interpreter.output_tensor(0);
  CHECK_CASE(output->dims->size == 2);
  CHECK_CASE(output->dims->data[0] == batches);
  CHECK_CASE(output->dims->data[1] == kWidth);
  for (int i = 0; i < count; ++i) {
    const int a = (i * 7) % 61 - 30;
    const int b = (i * 11) % 67 - 33;
    if (quantized) {
      const int expected = std::clamp(2 * (a + b) + 16, -128, 127);
      CHECK_CASE(interpreter.typed_output_tensor<int8_t>(0)[i] == expected);
    } else {
      CHECK_CASE(std::abs(interpreter.typed_output_tensor<float>(0)[i] -
                          (a * 0.25f + b * 0.5f)) < 1e-6f);
    }
  }
  return 0;
}

int CheckModel(bool quantized) {
  auto bytes = MakeModel(quantized);
  const auto* data = reinterpret_cast<const char*>(bytes.data());
  CHECK_CASE(!tflite::FlatBufferModel::VerifyAndBuildFromBuffer(
      data, bytes.size() / 2));
  auto model =
      tflite::FlatBufferModel::VerifyAndBuildFromBuffer(data, bytes.size());
  CHECK_CASE(model != nullptr);
  auto options = TfLiteXNNPackDelegateOptionsDefault();
  options.num_threads = 4;
  CHECK_CASE(options.flags & TFLITE_XNNPACK_DELEGATE_FLAG_QS8);
  std::unique_ptr<TfLiteDelegate, decltype(&TfLiteXNNPackDelegateDelete)>
      delegate(TfLiteXNNPackDelegateCreate(&options),
               TfLiteXNNPackDelegateDelete);
  CHECK_CASE(delegate != nullptr);
  tflite::ops::builtin::BuiltinOpResolverWithoutDefaultDelegates resolver;
  std::unique_ptr<tflite::Interpreter> interpreter;
  CHECK_CASE(tflite::InterpreterBuilder(*model, resolver)(&interpreter) ==
             kTfLiteOk);
  CHECK_CASE(interpreter != nullptr);
  CHECK_CASE(Infer(*interpreter, quantized, 1) == 0);
  CHECK_CASE(interpreter->ModifyGraphWithDelegate(delegate.get()) == kTfLiteOk);
  CHECK_CASE(interpreter->execution_plan().size() == 1);
  const auto* node =
      interpreter->node_and_registration(interpreter->execution_plan()[0]);
  CHECK_CASE(node != nullptr);
  CHECK_CASE(node->first.delegate == delegate.get());
  CHECK_CASE(node->second.builtin_code == kTfLiteBuiltinDelegate);
  CHECK_CASE(Infer(*interpreter, quantized, 1) == 0);
  CHECK_CASE(Infer(*interpreter, quantized, 3) == 0);
  return 0;
}

int main(int argc, char** argv) {
  base::AtExitManager at_exit;
  base::CommandLine::Init(argc, argv);
  base::ThreadPoolInstance::CreateAndStartWithDefaultParams("TFLite");
  CHECK_CASE(CheckModel(false) == 0);
  CHECK_CASE(CheckModel(true) == 0);
  base::ThreadPoolInstance::Get()->Shutdown();
  std::puts(
      "TFLite/XNNPACK: float, int8, delegation, reshape, invalid model passed");
  return 0;
}
