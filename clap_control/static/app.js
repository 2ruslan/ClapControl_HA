'use strict';
const $ = id => document.getElementById(id);
let settings, selected = [], catalog = [];
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-Clap-Control':'1'}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function message(text) { $('message').textContent = text; }
function renderScenes() {
  $('scenes').replaceChildren();
  selected.forEach((id, index) => {
    const item = document.createElement('li'), label = document.createElement('span');
    const scene = catalog.find(x => x.entity_id === id);
    label.textContent = scene ? `${scene.name} · ${id}${scene.available ? '' : ' (недоступна)'}` : id;
    item.append(label);
    [['↑',-1],['↓',1],['Видалити',0]].forEach(([text, direction]) => {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
      button.setAttribute('aria-label', `${text === '↑' ? 'Вище' : text === '↓' ? 'Нижче' : text}: ${id}`);
      button.disabled = direction === -1 && index === 0 || direction === 1 && index === selected.length-1;
      button.onclick = () => { if (!direction) selected.splice(index,1); else [selected[index],selected[index+direction]]=[selected[index+direction],selected[index]]; renderScenes(); };
      item.append(button);
    });
    $('scenes').append(item);
  });
}
async function refresh() {
  catalog = await api('api/scenes'); $('available').replaceChildren();
  catalog.forEach(scene => { const option = document.createElement('option'); option.value = scene.entity_id; option.textContent = `${scene.name} · ${scene.entity_id}${scene.available ? '' : ' (недоступна)'}`; $('available').append(option); });
  renderScenes();
}
$('add').onclick = () => { if ($('available').value) {selected.push($('available').value); renderScenes();} };
$('refresh').onclick = () => refresh().catch(e => message(e.message));
$('settings').onsubmit = async event => {
  event.preventDefault(); if (!settings) return;
  const value = {...settings, scenes:[...selected]};
  ['enabled','test_mode','emit_event'].forEach(id => value[id] = $(id).checked);
  ['clap_count','sensitivity','max_interval_ms','cooldown_seconds'].forEach(id => value[id] = Number($(id).value));
  ['audio_source'].forEach(id => value[id] = $(id).value);
  $('save').disabled = true;
  try {settings = await api('api/settings',value); message('Налаштування збережено.');}
  catch(e) {message(e.message);} finally {$('save').disabled=false;}
};
async function poll() {
  try {
    const s = await api('api/status');
    const names = {running:'Працює',disabled:'Вимкнений',error:'Помилка',connected:'Підключений',connecting:'Підключення',stopped:'Зупинений'};
    const rows = [['Детектор',names[s.detector_status]],['Мікрофон',names[s.audio_status]],['Тестування',s.test_mode?'Увімкнено':'Вимкнено'],['Хлопків / серій',`${s.claps} / ${s.sequences}`],['Активацій',s.activations],['Остання серія',s.last_trigger ? new Date(s.last_trigger).toLocaleString('uk-UA') : 'Ще не було'],['Остання активована сцена',s.last_scene || 'Ще не було'],['Номер останньої активації',s.scene_number],['Сцен у поточному списку',s.total_scenes],['Макс. RMS / фон / макс. peak (1 с)',`${s.level} / ${s.noise} / ${s.peak}`],['Поріг RMS',s.threshold]];
    if (s.last_analysis) {
      const a=s.last_analysis;
      const reasons={accepted:'Хлопок розпізнано',duration:'Задовгий імпульс / відлуння',spectrum:'Мало високих частот',tonal:'Тональний звук',onset:'Недостатньо різкий початок'};
      rows.push(['Останній аналіз імпульсу', `${reasons[a.reason] || a.reason} · ${a.duration_ms} мс · RMS ${a.rms} / поріг ${a.threshold} · ВЧ ${a.high_ratio ?? '—'} / пласкість ${a.flatness ?? '—'}`]);
    }
    $('status').replaceChildren();
    rows.forEach(([label,value]) => {const div=document.createElement('div'), small=document.createElement('small');div.className='metric';small.textContent=label;div.append(small,document.createTextNode(String(value)));$('status').append(div);});
    $('level').value=s.level; $('errors').textContent=[s.audio_error,s.error,s.event_error].filter(Boolean).join(' · ');
  } catch(e) {$('errors').textContent='Немає зв’язку з застосунком: '+e.message;}
  setTimeout(poll,1000);
}
(async () => {
  try {settings=await api('api/settings');selected=[...settings.scenes];Object.entries(settings).forEach(([id,value])=>{if ($(id) && id!=='scenes') {if(typeof value==='boolean') $(id).checked=value;else $(id).value=value;}});renderScenes();$('save').disabled=false;await refresh();}
  catch(e) {message(e.message);}
  poll();
})();
