# SPDX-License-Identifier: Apache-2.0
"""Check native parser output against Mojo's control-protocol wire contract."""

import sys
import unittest

from mojom.generate import module
from mojom.generate import pack


class ControlProtocolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(sys.argv[1], 'rb') as stream:
            cls.protocol = module.Module.Load(stream)
        cls.structs = {item.mojom_name: item for item in cls.protocol.structs}
        cls.unions = {item.mojom_name: item for item in cls.protocol.unions}

    def test_control_message_ids(self):
        self.assertEqual(self.protocol.mojom_namespace, 'mojo.interface_control')
        constants = {item.mojom_name: int(str(item.value), 0)
                     for item in self.protocol.constants}
        self.assertEqual(constants['kRunMessageId'], 0xffffffff)
        self.assertEqual(constants['kRunOrClosePipeMessageId'], 0xfffffffe)

    def test_version_query_and_wire_layout(self):
        result = self.structs['QueryVersionResult']
        self.assertEqual(len(result.fields), 1)
        self.assertEqual(result.fields[0].mojom_name, 'version')
        self.assertEqual(result.fields[0].kind.spec, module.UINT32.spec)
        version = pack.GetVersionInfo(pack.PackedStruct(result))
        self.assertEqual([(v.version, v.num_fields, v.num_bytes) for v in version],
                         [(0, 1, 16)])
        request = pack.GetVersionInfo(pack.PackedStruct(self.structs['RunMessageParams']))
        self.assertEqual([(v.version, v.num_fields, v.num_bytes) for v in request],
                         [(0, 1, 24)])

    def test_control_union_and_nullable_response(self):
        self.assertEqual([field.mojom_name for field in self.unions['RunInput'].fields],
                         ['query_version', 'flush_for_testing'])
        response = self.structs['RunResponseMessageParams'].fields[0]
        self.assertEqual(response.mojom_name, 'output')
        self.assertTrue(response.kind.is_nullable)
        self.assertEqual(response.kind.mojom_name, 'RunOutput')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])
