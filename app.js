"use strict";
const $ = (id) => document.getElementById(id);
const EXPECTED_VERSION = "0.3.0";
const state = {
  project: null,
  document: null,
  ai: null,
  busy: false,
  tab: "dashboard",
  dashboard: null,
  proposal: null,
};
const labels = {
  ready: "Semua halaman terbaca",
  partial: "Sebagian halaman terbaca",
  unreadable: "Teks belum terbaca",
  read: "Terbaca",
  needs_ocr: "Perlu OCR",
  failed: "Pembacaan gagal",
};
const kinds = { journal: "Jurnal", proposal: "Proposal", guideline: "Pedoman" };
const fieldLabels = {
  tujuan: "Tujuan",
  metode: "Metode",
  sampel: "Sampel",
  temuan: "Temuan",
  keterbatasan: "Keterbatasan",
};
const reviewLabels = {
  needs_review: "Belum ditinjau",
  reviewed: "Tinjauan tercatat pada teks terbaca",
  reviewed_partial: "Tinjauan parsial; ada halaman belum terbaca",
  needs_revision: "Perlu revisi",
  unknown: "Belum dapat dinilai",
  stale: "Versi sumber belum cocok; analisis ulang",
  superseded: "Riwayat analisis sebelumnya",
  failed: "Gagal",
};
const proposalLabels = {
  not_uploaded: "Belum ada proposal",
  not_audited: "Proposal siap diperiksa",
  structure_only: "Struktur sudah diperiksa",
  revisions_pending: "Ada revisi yang perlu ditindaklanjuti",
  unknown: "Ada kriteria belum dapat dinilai",
  partial: "Pembacaan proposal masih parsial",
  needs_reaudit: "Tindak lanjut perlu diperiksa ulang",
  needs_human_review: "Draf audit memerlukan tinjauan manusia",
  stale: "Integritas proposal perlu diperiksa",
};
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
async function api(path, options) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("Layanan tidak memberikan jawaban yang dapat dibaca.");
  }
  if (!response.ok) throw Error(data.error || "Operasi gagal.");
  return data;
}
function jsonPost(data) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  };
}
function lock(busy) {
  state.busy = busy;
  for (const node of document.querySelectorAll("button,input,select,textarea"))
    node.disabled = busy || node.dataset.unavailable === "true";
  updateAnalyze();
  if (typeof updateProposalControls === "function") updateProposalControls();
}
function updateAnalyze() {
  const d = state.document;
  const readable =
    d?.kind === "journal" &&
    d.source_integrity === "matched" &&
    d.extraction.pages.some((p) => p.status === "read");
  $("analyze").disabled =
    state.busy ||
    !readable ||
    state.ai?.status !== "configured" ||
    !$("consent").checked;
}
function setView(view) {
  state.tab = view;
  const library = view === "proposal" || view === "literature";
  $("view-dashboard").hidden = view !== "dashboard";
  $("view-library").hidden = !library;
  $("view-revisions").hidden = view !== "revisions";
  for (const node of document.querySelectorAll("nav [data-view]"))
    node.setAttribute("aria-pressed", String(node.dataset.view === view));
  $("view-label").textContent = {
    dashboard: "RINGKASAN",
    proposal: "PROPOSAL & AUDIT",
    literature: "LITERATUR",
    revisions: "DAFTAR REVISI",
  }[view];
  if (library) {
    $("library-eyebrow").textContent =
      view === "proposal" ? "PROPOSAL & PEDOMAN" : "LITERATUR & BUKTI";
    $("library-title").textContent =
      view === "proposal"
        ? "Mulai dari proposal Anda."
        : "Baca jurnal dan telusuri buktinya.";
    $("collection-title").textContent =
      view === "proposal" ? "Proposal dan pedoman" : "Jurnal penelitian";
    $("document-kind").value = view === "proposal" ? "proposal" : "journal";
    renderDocuments();
  }
}
async function navigate(view) {
  if (!state.project) {
    message("Buat atau pilih proyek terlebih dahulu.");
    $("new-project").open = true;
    $("title").focus();
    return;
  }
  lock(true);
  try {
    state.document = null;
    state.proposal = null;
    $("document").hidden = true;
    await refreshDashboard();
    setView(view);
  } catch (error) {
    message(error.message, true);
  } finally {
    lock(false);
  }
}
async function refreshProjects() {
  const data = await api("/api/projects");
  $("projects").replaceChildren();
  for (const project of data.projects) {
    const button = el("button");
    button.append(el("span", project.title));
    button.type = "button";
    button.setAttribute(
      "aria-pressed",
      String(state.project?.id === project.id),
    );
    button.title = project.title;
    button.addEventListener("click", () =>
      chooseProject(project).catch((e) => message(e.message, true)),
    );
    $("projects").append(button);
  }
  if (!data.projects.length)
    $("projects").append(el("small", "Belum ada proyek."));
  return data.projects;
}
async function chooseProject(project) {
  lock(true);
  try {
    state.project = project;
    state.document = null;
    state.proposal = null;
    $("document").hidden = true;
    $("project-name").textContent = project.title;
    $("project-name").title = project.title;
    $("project-subtitle").textContent =
      "Sumber, audit proposal, dan tindak lanjut penelitian dalam satu ruang kerja.";
    localStorage.setItem("skripsi-project", project.id);
    await Promise.all([refreshProjects(), refreshDashboard()]);
    setView("dashboard");
    $("new-project").open = false;
    message("Proyek dipilih. Lanjutkan dari langkah yang dibutuhkan.");
  } finally {
    lock(false);
  }
}
async function refreshDashboard() {
  if (!state.project) return;
  state.dashboard = await api(`/api/projects/${state.project.id}/dashboard`);
  renderDashboard();
  renderDocuments();
  if (typeof renderRevisions === "function") renderRevisions();
}
function renderDashboard() {
  const d = state.dashboard;
  if (!d) return;
  $("stat-proposal").textContent = d.counts.proposal;
  $("stat-journal").textContent = d.counts.journal;
  $("stat-issues").textContent = d.counts.open_issues;
  $("nav-issue-count").textContent = d.counts.open_issues;
  $("stat-addressed").textContent =
    `${d.counts.addressed} temuan ditandai ditangani`;
  $("next-title").textContent = proposalLabels[d.proposal_status];
  $("next-action").textContent = d.next_action;
  $("start-proposal").textContent = d.active_proposal_id
    ? "Buka proposal aktif"
    : "Unggah proposal";
  $("recent-documents").replaceChildren();
  for (const doc of d.documents.slice(0, 5)) {
    const row = el("div", undefined, "recent-row"),
      button = el("button", doc.filename);
    button.type = "button";
    button.addEventListener("click", () =>
      openDocument(doc.id).catch((e) => message(e.message, true)),
    );
    row.append(
      button,
      el(
        "small",
        kinds[doc.kind] + (doc.id === d.active_proposal_id ? " · aktif" : ""),
      ),
    );
    $("recent-documents").append(row);
  }
  if (!d.documents.length)
    $("recent-documents").append(
      el(
        "p",
        "Belum ada dokumen. Unggah proposal atau jurnal untuk memulai.",
        "blank-state",
      ),
    );
}
function renderDocuments() {
  const list = $("documents");
  list.replaceChildren();
  if (!state.dashboard) {
    list.append(el("p", "Pilih proyek terlebih dahulu.", "blank-state"));
    return;
  }
  const documents = state.dashboard.documents.filter((d) =>
    state.tab === "literature" ? d.kind === "journal" : d.kind !== "journal",
  );
  for (const doc of documents) {
    const button = el("button", doc.filename);
    button.type = "button";
    button.setAttribute("aria-pressed", String(state.document?.id === doc.id));
    button.append(
      el(
        "small",
        `${kinds[doc.kind]}${doc.id === state.dashboard.active_proposal_id ? " · aktif" : ""} · ${labels[doc.status]}`,
      ),
    );
    button.addEventListener("click", () =>
      openDocument(doc.id).catch((e) => message(e.message, true)),
    );
    list.append(button);
  }
  if (!documents.length)
    list.append(el("p", "Belum ada dokumen pada ruang ini.", "blank-state"));
}
async function openDocument(id) {
  lock(true);
  try {
    const doc = await api(`/api/documents/${id}`);
    if (!state.dashboard || state.dashboard.project.id !== doc.project_id)
      await refreshDashboard();
    setView(doc.kind === "journal" ? "literature" : "proposal");
    showDocument(doc);
    if (doc.kind === "proposal") await loadProposal(doc.id);
    renderDocuments();
  } finally {
    lock(false);
  }
}
function showDocument(doc) {
  state.document = doc;
  state.proposal = null;
  $("document").hidden = false;
  $("consent").checked = false;
  $("proposal-consent").checked = false;
  $("analysis-progress").textContent = "";
  $("proposal-progress").textContent = "";
  $("document-title").textContent = doc.filename;
  $("document-kind-label").textContent =
    kinds[doc.kind].toUpperCase() + " / PEMBACAAN SUMBER";
  $("document-meta").textContent =
    `${doc.extraction.pages.length} halaman PDF · ${(doc.size / 1024).toFixed(1)} KiB · ${new Date(doc.created_at).toLocaleString("id-ID")}`;
  $("extraction-status").textContent =
    doc.source_integrity === "matched"
      ? labels[doc.status]
      : "PDF sumber berubah atau tidak tersedia";
  $("checksum").textContent = "SHA-256: " + doc.sha256;
  $("original").href = `/api/documents/${doc.id}/pdf`;
  $("original").hidden = doc.source_integrity !== "matched";
  $("journal-panel").hidden = doc.kind !== "journal";
  $("proposal-panel").hidden = doc.kind !== "proposal";
  $("guideline-panel").hidden = doc.kind !== "guideline";
  $("page").replaceChildren(
    ...doc.extraction.pages.map((p) => {
      const option = el("option", `${p.pdf_page} · ${labels[p.status]}`);
      option.value = p.pdf_page;
      return option;
    }),
  );
  showPage(1);
  if (doc.kind === "journal") renderAnalyses();
  updateAnalyze();
}
function showPage(number, quote) {
  const page = state.document?.extraction.pages.find(
    (p) => p.pdf_page === number,
  );
  if (!page) {
    message("Halaman bukti tidak tersedia pada versi pembacaan ini.", true);
    return;
  }
  $("page").value = number;
  $("page-message").hidden = !page.message;
  $("page-message").textContent = page.message || "";
  const target = $("page-text");
  target.replaceChildren();
  const start = quote ? page.text.indexOf(quote) : -1;
  if (start >= 0)
    target.append(
      document.createTextNode(page.text.slice(0, start)),
      el("mark", quote),
      document.createTextNode(page.text.slice(start + quote.length)),
    );
  else
    target.textContent =
      page.text || "Tidak ada teks terbaca pada halaman ini.";
  if (state.document.kind === "proposal") $("finding-page").value = number;
  if (quote) {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.querySelector("mark")?.scrollIntoView({ block: "nearest" });
  }
}
async function openEvidence(evidence) {
  if (state.document?.id !== evidence.document_id)
    await openDocument(evidence.document_id);
  showPage(evidence.pdf_page, evidence.quote);
}
function evidenceNodes(evidence, container) {
  for (const item of evidence) {
    container.append(el("blockquote", item.quote));
    const button = el(
      "button",
      `Lihat bukti · halaman PDF ${item.pdf_page}`,
      "evidence-link",
    );
    button.type = "button";
    button.addEventListener("click", () =>
      openEvidence(item).catch((e) => message(e.message, true)),
    );
    container.append(button);
  }
}
for (const node of document.querySelectorAll("[data-view]"))
  node.addEventListener("click", () => navigate(node.dataset.view));
$("start-proposal").addEventListener("click", () => {
  if (!state.project) return navigate("proposal");
  if (state.dashboard?.active_proposal_id)
    openDocument(state.dashboard.active_proposal_id).catch((e) =>
      message(e.message, true),
    );
  else navigate("proposal");
});
$("project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  lock(true);
  try {
    const project = await api(
      "/api/projects",
      jsonPost({ title: $("title").value }),
    );
    $("project-form").reset();
    await chooseProject(project);
    message("Proyek tersimpan. Dashboard penelitian siap digunakan.");
  } catch (error) {
    message(error.message, true);
  } finally {
    lock(false);
  }
});
$("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.project) return;
  const file = $("pdf").files[0];
  if (!file) return;
  if (
    !file.name.toLowerCase().endsWith(".pdf") ||
    file.size > 15 * 1024 * 1024 ||
    !file.size
  ) {
    message("Pilih PDF berukuran 1 byte sampai 15 MiB.", true);
    return;
  }
  lock(true);
  message("Menyimpan sumber asli dan membaca setiap halaman…");
  try {
    const doc = await api(`/api/projects/${state.project.id}/documents`, {
      method: "POST",
      headers: {
        "Content-Type": "application/pdf",
        "X-Filename": encodeURIComponent(file.name),
        "X-Document-Kind": $("document-kind").value,
      },
      body: file,
    });
    await refreshDashboard();
    await openDocument(doc.id);
    $("upload-form").reset();
    $("document-kind").value = doc.kind;
    message(`${kinds[doc.kind]} tersimpan. ${labels[doc.status]}.`);
  } catch (error) {
    message(error.message, true);
  } finally {
    lock(false);
  }
});
$("page").addEventListener("change", () => showPage(Number($("page").value)));
async function initialize() {
  const [health, ai] = await Promise.all([
    api("/api/health"),
    api("/api/ai/status"),
  ]);
  $("app-version").textContent =
    `v${health.version || "lama"} · Dashboard & audit proposal`;
  if (health.version !== EXPECTED_VERSION) {
    $("capability-status").textContent =
      "Server versi lama masih berjalan. Hentikan server dengan Ctrl+C lalu jalankan kode terbaru.";
    message(
      "Versi halaman dan server berbeda. Restart server dari folder kode terbaru.",
      true,
    );
    return;
  }
  state.ai = ai;
  $("stat-ai").textContent =
    ai.status === "configured" ? "Dikonfigurasi" : "Belum dikonfigurasi";
  $("capability-status").textContent =
    ai.status === "configured"
      ? "AI dikonfigurasi · setiap audit isi memerlukan izin pengiriman teks. Koneksi dan kuota diperiksa saat digunakan."
      : "AI belum dikonfigurasi · pembacaan PDF, pemeriksaan struktur, dan pencatatan temuan manual tetap tersedia.";
  $("ai-status").textContent =
    ai.status === "configured" ? "AI dikonfigurasi" : "Belum dikonfigurasi";
  $("ai-message").textContent = ai.message;
  const projects = await refreshProjects();
  const saved = localStorage.getItem("skripsi-project");
  const selected = projects.find((p) => p.id === saved) || projects[0];
  if (selected) await chooseProject(selected);
  lock(false);
}
document.addEventListener("DOMContentLoaded", () =>
  initialize().catch((e) => message(e.message, true)),
);
