'use strict';
const $ = id => document.getElementById(id);
const state = {project: null, document: null, ai: null, busy: false};
const labels = {ready: 'Semua halaman terbaca', partial: 'Sebagian halaman terbaca', unreadable: 'Teks belum terbaca', read: 'Terbaca', needs_ocr: 'Perlu OCR', failed: 'Pembacaan gagal'};
const fieldLabels = {tujuan:'Tujuan', metode:'Metode', sampel:'Sampel', temuan:'Temuan', keterbatasan:'Keterbatasan'};
const reviewLabels = {needs_review:'Belum ditinjau', reviewed:'Tinjauan tercatat pada teks terbaca', reviewed_partial:'Tinjauan parsial; ada halaman belum terbaca', needs_revision:'Perlu revisi', unknown:'Belum dapat dinilai', stale:'Versi sumber belum cocok; analisis ulang', superseded:'Riwayat analisis sebelumnya', failed:'Gagal'};
function el(tag, text, className) { const node=document.createElement(tag); if(text!==undefined) node.textContent=text; if(className) node.className=className; return node; }
function message(text, error=false) { $('message').textContent=text; $('message').classList.toggle('error',error); }
async function api(path, options) {
  const response=await fetch(path,options); let data;
  try { data=await response.json(); } catch { throw Error('Layanan tidak memberikan jawaban yang dapat dibaca.'); }
  if(!response.ok) throw Error(data.error || 'Operasi gagal.');
  return data;
}
function jsonPost(data) { return {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}; }
function lock(busy) {
  state.busy=busy;
  for(const node of document.querySelectorAll('button, input, select, textarea')) node.disabled=busy;
  updateAnalyze();
}
function updateAnalyze() {
  const doc=state.document;
  const readable=doc && doc.source_integrity==='matched' && doc.extraction.pages.some(p=>p.status==='read');
  $('analyze').disabled=state.busy || !readable || state.ai?.status!=='configured' || !$('consent').checked;
}
async function refreshProjects() {
  const data=await api('/api/projects'); $('projects').replaceChildren();
  if(!data.projects.length) $('projects').append(el('small','Belum ada proyek.'));
  for(const project of data.projects) {
    const button=el('button',project.title); button.type='button'; button.dataset.id=project.id;
    button.setAttribute('aria-pressed',String(state.project?.id===project.id));
    button.addEventListener('click',()=>chooseProject(project).catch(e=>message(e.message,true)));
    $('projects').append(button);
  }
}
async function chooseProject(project) {
  lock(true);
  try {
    state.project=project; state.document=null; $('document').hidden=true; $('empty').hidden=false;
    $('project-title').textContent=project.title; $('upload-section').hidden=false;
    await refreshProjects(); await refreshDocuments(); message('Proyek dipilih. Unggah atau pilih jurnal.');
  } finally { lock(false); }
}
async function refreshDocuments() {
  const data=await api(`/api/projects/${state.project.id}/documents`); $('documents').replaceChildren();
  if(!data.documents.length) $('documents').append(el('small','Belum ada PDF di proyek ini.'));
  for(const doc of data.documents) {
    const button=el('button',doc.filename); button.type='button'; button.dataset.id=doc.id;
    button.setAttribute('aria-pressed',String(state.document?.id===doc.id));
    button.append(el('small',labels[doc.status]));
    button.addEventListener('click',()=>openDocument(doc.id).catch(e=>message(e.message,true)));
    $('documents').append(button);
  }
}
async function openDocument(id) {
  lock(true);
  try { showDocument(await api(`/api/documents/${id}`)); await refreshDocuments(); }
  finally { lock(false); }
}
function showDocument(doc) {
  state.document=doc; $('analysis-progress').textContent=''; $('empty').hidden=true; $('document').hidden=false; $('consent').checked=false;
  $('document-title').textContent=doc.filename;
  $('document-meta').textContent=`${doc.extraction.pages.length} halaman PDF · ${(doc.size/1024).toFixed(1)} KiB · ${new Date(doc.created_at).toLocaleString('id-ID')}`;
  $('extraction-status').textContent=labels[doc.status];
  if(doc.source_integrity!=='matched') $('extraction-status').textContent='PDF sumber berubah atau tidak tersedia';
  $('checksum').textContent='SHA-256: '+doc.sha256;
  $('original').href=`/api/documents/${doc.id}/pdf`;
  $('original').hidden=doc.source_integrity!=='matched';
  $('page').replaceChildren(...doc.extraction.pages.map(p=>{ const option=el('option',`${p.pdf_page} · ${labels[p.status]}`); option.value=p.pdf_page; return option; }));
  showPage(1); renderAnalyses(); updateAnalyze();
}
function showPage(number, quote) {
  const page=state.document.extraction.pages.find(p=>p.pdf_page===number);
  if(!page) { message('Halaman bukti tidak tersedia pada versi pembacaan ini.',true); return; }
  $('page').value=number; $('page-message').hidden=!page.message; $('page-message').textContent=page.message || '';
  const target=$('page-text'); target.replaceChildren();
  const start=quote ? page.text.indexOf(quote) : -1;
  if(start>=0) target.append(document.createTextNode(page.text.slice(0,start)),el('mark',quote),document.createTextNode(page.text.slice(start+quote.length)));
  else target.textContent=page.text || 'Tidak ada teks terbaca pada halaman ini.';
  if(quote) { target.scrollIntoView({behavior:'smooth',block:'center'}); const mark=target.querySelector('mark'); if(mark) mark.scrollIntoView({block:'nearest'}); }
}
function renderAnalyses() {
  $('analysis-results').replaceChildren(); $('history').replaceChildren();
  const history=state.document.analyses;
  $('history-panel').hidden=!history.length;
  for(const record of history) {
    $('history').append(el('p',`${new Date(record.created_at).toLocaleString('id-ID')} · ${reviewLabels[record.review_state] || 'Belum ditinjau'} · ${record.result.model || record.result.message || ''}`,'muted'));
    for(const review of record.reviews || []) $('history').append(el('p',`${review.details.reviewer} · ${reviewLabels[review.status]} · ${new Date(review.created_at).toLocaleString('id-ID')} · ${review.details.note}`,'muted'));
  }
  const record=history.find(r=>r.status==='needs_review');
  if(!record) { $('analysis-results').append(el('p','Belum ada hasil analisis.','muted')); return; }
  const result=record.result;
  $('analysis-results').append(el('p',result.message,'notice'));
  $('analysis-results').append(el('p',`Model: ${result.model} · ${new Date(record.created_at).toLocaleString('id-ID')} · ${result.read_pages.length} halaman terbaca`,'muted'));
  if(result.unread_pages.length) $('analysis-results').append(el('p',`Cakupan parsial. Halaman tidak terbaca: ${result.unread_pages.join(', ')}. “Tidak ditemukan” hanya berlaku pada teks yang terbaca.`,'notice'));
  for(const [key,label] of Object.entries(fieldLabels)) {
    const field=result.fields[key], card=el('div',undefined,'analysis-card'); card.append(el('h3',label));
    if(field.status==='not_found') card.append(el('p','Tidak ditemukan pada teks yang terbaca. Periksa sumber asli; ini bukan bukti bahwa informasi tersebut tidak ada.','not-found'));
    for(const claim of field.claims) {
      card.append(el('p',claim.text));
      for(const evidence of claim.evidence) {
        card.append(el('blockquote',evidence.quote));
        if(record.review_state==='stale') {
          card.append(el('small',`Bukti versi lama · halaman PDF ${evidence.pdf_page}. Analisis ulang sebelum memakai bukti pada versi saat ini.`));
          continue;
        }
        const button=el('button',`Lihat bukti · halaman PDF ${evidence.pdf_page}`,'evidence-link'); button.type='button';
        button.addEventListener('click',()=>showPage(evidence.pdf_page,evidence.quote)); card.append(button);
      }
    }
    $('analysis-results').append(card);
  }
  renderReview(record);
}
function renderReview(record) {
  const section=el('div',undefined,'review-panel');
  section.append(el('h4','Tinjauan bukti oleh pengguna'));
  section.append(el('p',reviewLabels[record.review_state] || 'Belum ditinjau','notice'));
  section.append(el('small','Catatan ini bukan persetujuan pembimbing atau verifikasi identitas. Periksa seluruh klaim, konteks, dan halaman sumber sebelum mencatat keputusan.'));
  $('analysis-results').append(section);
  if(record.review_state==='stale' || record.review_state==='superseded') return;
  const previous=record.reviews?.[0]?.details;
  const form=el('form'); form.id='human-review-form';
  function input(labelText, id, tag='input') {
    const label=el('label',labelText); label.htmlFor=id;
    const node=el(tag); node.id=id; node.required=true; form.append(label,node); return node;
  }
  const reviewer=input('Nama peninjau (catatan lokal)','reviewer'); reviewer.maxLength=100;
  reviewer.value=previous?.reviewer || '';
  const decisions={};
  for(const [key,label] of Object.entries(fieldLabels)) {
    const select=input(`Tinjauan ${label}`,'review-'+key,'select'); decisions[key]=select;
    const found=record.result.fields[key].status==='found';
    for(const [value,text] of [['unknown','Belum dapat dinilai'], ['needs_revision','Perlu revisi'],
      [found?'supported':'not_found_in_readable_text',found?'Seluruh klaim bagian ini didukung bukti':'Tidak ditemukan pada teks terbaca; cakupan diperiksa']]) {
      const option=el('option',text); option.value=value; select.append(option);
    }
    select.value=previous?.decisions[key] || 'unknown';
  }
  const note=input('Alasan dan batas tinjauan','review-note','textarea'); note.maxLength=2000;
  const button=el('button','Simpan catatan tinjauan'); button.type='submit'; form.append(button);
  section.append(form);
  const documentId=state.document.id;
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const payload={analysis_id:record.id, source_sha256:record.result.source_sha256,
      extraction_sha256:record.result.extraction_sha256, reviewer:reviewer.value, note:note.value,
      decisions:Object.fromEntries(Object.entries(decisions).map(([key,node])=>[key,node.value]))};
    lock(true);
    try {
      await api(`/api/documents/${documentId}/reviews`,jsonPost(payload));
      state.document=await api(`/api/documents/${documentId}`); renderAnalyses();
      message('Tinjauan tersimpan untuk versi analisis ini.');
    } catch(error) { message(error.message,true); }
    finally { lock(false); }
  });
}
$('project-form').addEventListener('submit',async event=>{
  event.preventDefault(); lock(true); message('Menyimpan proyek…');
  try { const project=await api('/api/projects',jsonPost({title:$('title').value})); $('project-form').reset(); await chooseProject(project); message('Proyek tersimpan.'); }
  catch(e) { message(e.message,true); } finally { lock(false); }
});
$('upload-form').addEventListener('submit',async event=>{
  event.preventDefault(); const file=$('pdf').files[0]; if(!file) return;
  if(!file.name.toLowerCase().endsWith('.pdf') || file.size>15*1024*1024 || !file.size) { message('Pilih PDF berukuran 1 byte sampai 15 MiB.',true); return; }
  lock(true); message('Menyimpan PDF dan membaca teks per halaman…');
  try {
    const doc=await api(`/api/projects/${state.project.id}/documents`,{method:'POST',headers:{'Content-Type':'application/pdf','X-Filename':encodeURIComponent(file.name)},body:file});
    showDocument(doc); await refreshDocuments(); $('upload-form').reset(); message(labels[doc.status]+'. PDF asli tersimpan.');
  } catch(e) { message(e.message,true); } finally { lock(false); }
});
$('page').addEventListener('change',()=>showPage(Number($('page').value)));
$('consent').addEventListener('change',updateAnalyze);
$('analyze').addEventListener('click',async()=>{
  lock(true); $('analysis-progress').textContent='Menganalisis dan memeriksa kutipan…';
  try {
    await api(`/api/documents/${state.document.id}/analyze`,jsonPost({consent:true}));
    state.document=await api(`/api/documents/${state.document.id}`); renderAnalyses();
    $('analysis-progress').textContent='Analisis tersimpan sebagai draf. Tinjau setiap klaim dengan sumbernya.';
  } catch(e) {
    $('analysis-progress').textContent=e.message;
    try { state.document=await api(`/api/documents/${state.document.id}`); renderAnalyses(); } catch { /* Keep the prior visible result. */ }
  } finally { lock(false); }
});
async function initialize() {
  await refreshProjects(); state.ai=await api('/api/ai/status');
  $('ai-status').textContent=state.ai.status==='configured'?'AI dikonfigurasi':'Belum dikonfigurasi';
  $('ai-message').textContent=state.ai.message+' Hanya teks halaman yang dikirim, setelah Anda memberi izin.';
  updateAnalyze();
}
initialize().catch(e=>message(e.message,true));
