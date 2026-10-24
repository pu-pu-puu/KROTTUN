// Decorative, illustrative locations only. No network, pywebview or app RPC.
const variant = new URLSearchParams(location.search).get('v') || '1';
document.body.dataset.variant = variant;
const svg = document.querySelector('.world-map-layer svg');
const ns = 'http://www.w3.org/2000/svg';
const dots = [...svg.querySelector('path').getAttribute('d').matchAll(/M ([\d.]+) ([\d.]+) m/g)].map(m => [+m[1], +m[2]]);
// The incumbent map is a stylized matrix; capital positions are mapped to its nearest dots.
const cities = [
  ['Вашингтон', -77.04, 38.91], ['Бразилиа', -47.88, -15.79],
  ['Лондон', -.13, 51.51], ['Париж', 2.35, 48.86], ['Берлин', 13.4, 52.52],
  ['Каир', 31.24, 30.04], ['Претория', 28.19, -25.75], ['Анкара', 32.86, 39.93],
  ['Нью-Дели', 77.21, 28.61], ['Пекин', 116.41, 39.90], ['Токио', 139.69, 35.68],
  ['Канберра', 149.13, -35.28], ['Джакарта', 106.85, -6.21]
];
function circle(x, y, r, cls, delay, label) {
  const el = document.createElementNS(ns, 'circle');
  for (const [key, val] of Object.entries({cx:x, cy:y, r, class:cls})) el.setAttribute(key, val);
  el.style.setProperty('--delay', `${delay}s`);
  if (label) { const title = document.createElementNS(ns, 'title'); title.textContent = label; el.append(title); }
  svg.append(el);
}
cities.forEach(([name, lon, lat], i) => {
  const px = (lon + 180) / 360 * 1000, py = (90 - lat) / 180 * 500;
  const [x, y] = dots.reduce((best, p) => Math.hypot(p[0]-px,p[1]-py) < Math.hypot(best[0]-px,best[1]-py) ? p : best);
  const delay = -(i * 1.43 + .8);
  if (variant === '1') circle(x, y, 12, 'halo', delay);
  if (variant === '2') circle(x, y, 8, 'ripple', delay);
  if (variant === '3') {
    dots.filter(p => Math.hypot(p[0]-x,p[1]-y) < 34).forEach(([dx,dy]) => circle(dx,dy,2.65,'cluster', delay));
  }
  circle(x, y, variant === '1' ? 3.6 : 3.1, 'capital', delay, name);
});
function pause(value) { document.body.classList.toggle('paused', value || document.hidden); }
let userPaused = false;
addEventListener('message', e => {
  if (e.source !== parent) return;
  if (e.data?.type === 'pause') { userPaused = e.data.value; pause(userPaused); }
  if (e.data?.type === 'focus') document.body.classList.toggle('focus', e.data.value);
});
document.addEventListener('visibilitychange', () => pause(userPaused));
document.querySelectorAll('button, .ip-pill, .toggle-track').forEach(el => { el.style.pointerEvents = 'none'; el.tabIndex = -1; });
