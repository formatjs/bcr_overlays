async function ready() {
  await document.fonts.ready;
  await Promise.all([...document.images].map(image => image.decode()));
  let pixel = null;
  const canvas = document.querySelector('canvas');
  if (canvas) {
    const context = canvas.getContext('2d');
    context.fillStyle = '#f6b44b';
    context.fillRect(0, 0, 280, 280);
    context.fillStyle = '#2b8bcf';
    context.fillRect(20, 20, 100, 100);
    context.fillStyle = '#15243a';
    context.beginPath();
    context.arc(190, 90, 54, 0, 2 * Math.PI);
    context.fill();
    context.fillStyle = '#ffffff';
    context.fillRect(25, 175, 230, 65);
    context.globalCompositeOperation = 'multiply';
    context.fillStyle = '#8f94fb';
    context.fillRect(65, 150, 100, 100);
    pixel = [...context.getImageData(25, 25, 1, 1).data];
  }
  const boxes = {};
  for (const id of ['scene', 'a', 'b', 'e']) {
    const element = document.getElementById(id);
    if (!element) continue;
    const {x, y, width, height} = element.getBoundingClientRect();
    boxes[id] = [x, y, width, height];
  }
  document.getElementById('result').textContent = JSON.stringify({
    ready: true, boxes, pixel, viewport: [innerWidth, innerHeight, devicePixelRatio],
  });
}
ready().catch(error => {
  document.getElementById('result').textContent = JSON.stringify({ready: false, error: String(error)});
});
