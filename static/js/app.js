// SANTUY - katalog: smart search, auto-suggestion, filter, sorting, lokasi
const $ = id => document.getElementById(id);
let userPos = null;   // {lat, lng}
let timer = null;
let sgIndex = -1;

function debounce(fn, ms){ clearTimeout(timer); timer = setTimeout(fn, ms); }

function params(){
  const p = new URLSearchParams();
  const q = $('q').value.trim();
  if (q) p.set('q', q);
  if ($('f-category').value) p.set('category', $('f-category').value);
  if ($('f-region').value) p.set('region', $('f-region').value);
  if ($('f-pmin').value) p.set('price_min', $('f-pmin').value);
  if ($('f-pmax').value) p.set('price_max', $('f-pmax').value);
  p.set('sort', $('sort').value);
  if (userPos){ p.set('lat', userPos.lat); p.set('lng', userPos.lng); }
  return p.toString();
}

function badgeClass(b){
  if (b === 'Terlaris') return 'b-Terlaris';
  if (b === 'Top Rated') return 'b-Top';
  return 'b-Stok';
}

async function load(){
  $('count').textContent = 'Memuat…';
  const res = await fetch('/api/products?' + params());
  const data = await res.json();
  $('count').textContent = `${data.count} produk ditemukan`;
  const grid = $('grid');
  if (!data.count){
    grid.innerHTML = '<div class="empty">Tidak ada produk yang cocok. Coba ubah kata kunci atau filter.</div>';
    return;
  }
  grid.innerHTML = data.items.map(p => {
    const stars = '★'.repeat(Math.round(p.rating)) + '☆'.repeat(5 - Math.round(p.rating));
    const dist = (p.distance_km != null) ? `<span class="dist">📍 ${p.distance_km} km</span>` : '';
    const badges = p.badges.map(b => `<span class="badge ${badgeClass(b)}">${b}</span>`).join('');
    return `<a class="card" href="/produk/${p.id}">
      <div class="thumb">${p.emoji}</div>
      <div class="body">
        <div class="pname">${p.name}</div>
        <div class="price">${p.price_str} <span class="unit">/${p.unit}</span></div>
        <div class="meta">🏪 ${p.umkm_name} ${p.verified ? '<span class="verified">✔</span>' : ''}</div>
        <div class="meta">📍 ${p.city}, ${p.region} ${dist}</div>
        <div class="meta"><span class="stars">${stars}</span> ${p.rating} (${p.rating_count}) · terjual ${p.sold}</div>
        <div class="badges"><span class="tier">${p.price_tier}</span>${badges}</div>
      </div></a>`;
  }).join('');
}

// ---- Auto-suggestion ----
const sg = $('suggest');
async function suggest(){
  const q = $('q').value.trim();
  if (!q){ sg.classList.remove('show'); return; }
  const res = await fetch('/api/suggest?q=' + encodeURIComponent(q));
  const list = await res.json();
  if (!list.length){ sg.classList.remove('show'); return; }
  sgIndex = -1;
  sg.innerHTML = list.map(s =>
    `<div data-text="${s.text}"><span>${s.icon}</span> ${s.text}<span class="stype">${s.type}</span></div>`
  ).join('');
  [...sg.children].forEach(el => {
    el.onclick = () => { $('q').value = el.dataset.text; sg.classList.remove('show'); load(); };
  });
  sg.classList.add('show');
}

$('q').addEventListener('input', () => { debounce(suggest, 180); debounce(load, 350); });
$('q').addEventListener('keydown', e => {
  const items = [...sg.querySelectorAll('div')];
  if (!sg.classList.contains('show') || !items.length){
    if (e.key === 'Enter') load();
    return;
  }
  if (e.key === 'ArrowDown'){ sgIndex = (sgIndex + 1) % items.length; e.preventDefault(); }
  else if (e.key === 'ArrowUp'){ sgIndex = (sgIndex - 1 + items.length) % items.length; e.preventDefault(); }
  else if (e.key === 'Enter'){
    if (sgIndex >= 0){ $('q').value = items[sgIndex].dataset.text; }
    sg.classList.remove('show'); load(); return;
  } else if (e.key === 'Escape'){ sg.classList.remove('show'); return; }
  items.forEach((el, i) => el.classList.toggle('active', i === sgIndex));
});
document.addEventListener('click', e => {
  if (!e.target.closest('.searchbox')) sg.classList.remove('show');
});

// ---- Filters & sorting ----
['f-category', 'f-region', 'sort'].forEach(id => $(id).addEventListener('change', load));
['f-pmin', 'f-pmax'].forEach(id => $(id).addEventListener('input', () => debounce(load, 400)));

$('reset').onclick = () => {
  ['q', 'f-pmin', 'f-pmax'].forEach(id => $(id).value = '');
  $('f-category').value = ''; $('f-region').value = ''; $('sort').value = 'relevan';
  load();
};

// ---- Pencarian berbasis lokasi (GPS) ----
$('geo-btn').onclick = () => {
  if (!navigator.geolocation){ $('loc-status').textContent = 'Browser tidak mendukung GPS.'; return; }
  $('loc-status').textContent = 'Meminta izin lokasi…';
  navigator.geolocation.getCurrentPosition(
    pos => {
      userPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      $('loc-status').innerHTML = '✅ Lokasi aktif. Aktifkan urut "Terdekat".';
      if ($('sort').value === 'relevan') $('sort').value = 'terdekat';
      load();
    },
    () => {
      // fallback: titik tengah Pulau Jawa untuk demo bila izin ditolak
      userPos = { lat: -7.0, lng: 110.0 };
      $('loc-status').innerHTML = '⚠️ Izin ditolak — pakai lokasi demo (Jawa Tengah).';
      load();
    }
  );
};

load();
