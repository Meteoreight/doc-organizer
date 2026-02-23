let documents = [];
let selected = null;
let sortKey = 'document_number';
let order = 'asc';
let lastMatchQuery = '';

async function loadDocuments() {
  const res = await fetch(`/api/documents?sort_by=${sortKey}&order=${order}`);
  documents = await res.json();
  renderRows(documents);
}

function highlight(text, q) {
  if (!q) return text || '';
  const i = (text || '').toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text || '';
  return `${text.slice(0,i)}<mark>${text.slice(i, i+q.length)}</mark>${text.slice(i+q.length)}`;
}

function renderRows(rows) {
  const tbody = document.getElementById('docRows');
  tbody.innerHTML = '';
  rows.forEach(d => {
    const tr = document.createElement('tr');
    if (selected && selected.id === d.id) tr.classList.add('selected');
    tr.innerHTML = `
      <td>${highlight(d.document_number, lastMatchQuery)}</td>
      <td>${highlight(d.name || '', lastMatchQuery)}</td>
      <td>${d.tags || ''}</td>
    `;
    tr.onclick = () => selectDoc(d);
    tbody.appendChild(tr);
  });
}

function selectDoc(d) {
  selected = d;
  document.getElementById('detailNumber').value = d.document_number || '';
  document.getElementById('detailName').value = d.name || '';
  document.getElementById('detailTags').value = d.tags || '';
  document.getElementById('detailSummary').value = d.summary || '';
  document.getElementById('detailVeeva').value = d.veeva_link || '';
  document.getElementById('chunkList').innerHTML = '';
  renderRows(documents);
}

async function addDocument() {
  const num = document.getElementById('docNumberInput').value.trim();
  if (!num) return;
  const res = await fetch('/api/documents', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({document_number: num})
  });
  if (!res.ok) alert(await res.text());
  await loadDocuments();
}

async function saveDetail() {
  if (!selected) return;
  const payload = {
    name: document.getElementById('detailName').value,
    tags: document.getElementById('detailTags').value,
    summary: document.getElementById('detailSummary').value,
    veeva_link: document.getElementById('detailVeeva').value,
  };
  await fetch(`/api/documents/${selected.id}`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  await loadDocuments();
}

async function regenerate() {
  if (!selected) return;
  const res = await fetch(`/api/documents/${selected.id}/regenerate`, {method:'POST'});
  if (!res.ok) alert(await res.text());
  await loadDocuments();
}

async function deleteDoc() {
  if (!selected) return;
  await fetch(`/api/documents/${selected.id}`, {method:'DELETE'});
  selected = null;
  await loadDocuments();
}

async function runMatchSearch() {
  lastMatchQuery = document.getElementById('matchQuery').value.trim();
  if (!lastMatchQuery) return loadDocuments();
  const res = await fetch('/api/search/match', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({query: lastMatchQuery})
  });
  const rows = await res.json();
  renderRows(rows);
}

async function runSemanticSearch() {
  const q = document.getElementById('semanticQuery').value.trim();
  if (!q) return;
  const res = await fetch('/api/search/semantic', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({query: q})
  });
  const data = await res.json();
  const docs = data.map(x => x.document);
  renderRows(docs);
  if (data[0]) {
    selectDoc(data[0].document);
    document.getElementById('chunkList').innerHTML = data[0].chunks.map(c => `<li>${c.chunk}</li>`).join('');
  }
}

function sortBy(key) {
  if (sortKey === key) order = order === 'asc' ? 'desc' : 'asc';
  else { sortKey = key; order = 'asc'; }
  loadDocuments();
}

async function importCsv() {
  const input = document.getElementById('csvInput');
  if (!input.files[0]) return;
  const form = new FormData();
  form.append('file', input.files[0]);
  const res = await fetch('/api/import', {method:'POST', body: form});
  if (!res.ok) alert(await res.text());
  await loadDocuments();
}

loadDocuments();
