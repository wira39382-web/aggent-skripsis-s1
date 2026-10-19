"use strict";
const auditLabels = {
  structure_only: "Struktur lokal diperiksa",
  draft_audit: "Draf audit AI",
  failed: "Audit gagal",
};
const checkLabels = {
  adequate: "Memadai menurut draf AI",
  needs_revision: "Perlu revisi",
  unknown: "Belum dapat dinilai",
};
const issueLabels = {
  open: "Terbuka",
  in_progress: "Sedang dikerjakan",
  addressed: "Ditandai ditangani",
};
const severityLabels = { critical: "Kritis", major: "Mayor", minor: "Minor" };
function updateProposalControls() {
  const d = state.document;
  const ready =
    d?.kind === "proposal" &&
    d.source_integrity === "matched" &&
    state.proposal?.is_active;
  $("structure-audit").disabled = state.busy || !ready;
  $("proposal-ai-audit").disabled =
    state.busy ||
    !ready ||
    !d?.extraction.pages.some((p) => p.status === "read") ||
    state.ai?.status !== "configured" ||
    !$("proposal-consent").checked;
  $("manual-finding").hidden = !ready;
  for (const node of $("finding-form").querySelectorAll(
    "button,input,select,textarea",
  ))
    node.disabled = state.busy || !ready;
}
async function loadProposal(id) {
  state.proposal = await api(`/api/documents/${id}/proposal`);
  renderProposal();
  updateProposalControls();
}
function selectedGuidelines() {
  return [...$("guideline-options").querySelectorAll("input:checked")].map(
    (n) => n.value,
  );
}
function renderProposal() {
  const view = state.proposal;
  if (!view) return;
  $("proposal-active-notice").textContent = view.is_active
    ? "Proposal aktif. Pemeriksaan struktur mengenali calon heading; mutu isi dan keputusan akademik memerlukan tinjauan."
    : "Versi proposal sebelumnya. Riwayat dapat dibaca; gunakan unggahan proposal terbaru untuk audit dan tindak lanjut.";
  if (state.document.source_integrity !== "matched")
    $("proposal-active-notice").textContent =
      "PDF sumber hilang/berubah. Pulihkan sumber atau unggah proposal baru sebelum mengaudit.";
  const outline = $("proposal-outline");
  outline.replaceChildren(el("h3", "Pemetaan calon Bab I–III"));
  for (const chapter of ["I", "II", "III"]) {
    const candidates = view.structure.outline.filter(
      (o) => o.chapter === chapter,
    );
    const row = el("div", undefined, "outline-row");
    row.append(el("span", `Bab ${chapter}`));
    if (!candidates.length) row.append(el("small", "Heading belum terdeteksi"));
    else {
      const button = el(
        "button",
        `Halaman ${[...new Set(candidates.map((o) => o.pdf_page))].join(", ")}`,
        "evidence-link",
      );
      button.type = "button";
      button.addEventListener("click", () =>
        showPage(candidates[0].pdf_page, candidates[0].quote),
      );
      row.append(button);
    }
    outline.append(row);
  }
  outline.append(el("p", view.structure.message));
  if (view.structure.unread_pages.length)
    outline.append(
      el(
        "p",
        `Halaman belum terbaca: ${view.structure.unread_pages.join(", ")}. OCR belum tersedia.`,
        "notice",
      ),
    );
  const previous = new Set(selectedGuidelines());
  $("guideline-options").replaceChildren();
  $("finding-guideline").replaceChildren();
  const none = el("option", "Tidak menyertakan bukti pedoman");
  none.value = "";
  $("finding-guideline").append(none);
  const guidelines = state.dashboard.documents.filter(
    (d) => d.kind === "guideline",
  );
  for (const doc of guidelines) {
    const label = el("label", undefined, "consent"),
      box = el("input");
    box.type = "checkbox";
    box.value = doc.id;
    box.checked = previous.has(doc.id);
    label.append(box, document.createTextNode(doc.filename));
    $("guideline-options").append(label);
    const option = el("option", doc.filename);
    option.value = doc.id;
    $("finding-guideline").append(option);
  }
  if (!guidelines.length)
    $("guideline-options").append(
      el(
        "p",
        "Belum ada pedoman pada proyek ini. Unggah dengan jenis “Pedoman kampus”.",
        "muted",
      ),
    );
  $("finding-criterion").replaceChildren();
  for (const [key, label] of Object.entries(view.criteria)) {
    const option = el("option", label);
    option.value = key;
    $("finding-criterion").append(option);
  }
  $("finding-page").value = $("page").value;
  $("finding-criterion").value = "keselarasan";
  $("proposal-checks").replaceChildren();
  const audit = view.audits.find((a) => a.status === "draft_audit");
  if (audit) {
    $("proposal-checks").append(
      el(
        "p",
        audit.fresh
          ? audit.result.message
          : "Arsip audit versi sebelumnya; hasil ini tidak berlaku untuk proposal/pedoman saat ini.",
        "notice",
      ),
    );
    $("proposal-checks").append(
      el(
        "p",
        `Model: ${audit.result.model} · ${new Date(audit.created_at).toLocaleString("id-ID")}`,
        "muted",
      ),
    );
    for (const [key, check] of Object.entries(audit.result.checks)) {
      const card = el("div", undefined, "check-card");
      card.append(
        el("h3", view.criteria[key]),
        el("span", checkLabels[check.status], "badge"),
        el("p", check.summary),
        el("p", "Tindak lanjut: " + check.recommendation),
      );
      if (audit.fresh) evidenceNodes(check.evidence, card);
      else
        for (const e of check.evidence) card.append(el("blockquote", e.quote));
      $("proposal-checks").append(card);
    }
  } else {
    $("proposal-checks").append(
      el(
        "p",
        "Audit substantif belum tersedia. Pemeriksaan struktur tidak menilai keselarasan metode atau kepatuhan kampus. Gunakan audit AI setelah dikonfigurasi, atau catat temuan manual dengan bukti.",
        "notice",
      ),
    );
  }
  $("proposal-history").replaceChildren();
  for (const a of view.audits)
    $("proposal-history").append(
      el(
        "p",
        `${new Date(a.created_at).toLocaleString("id-ID")} · ${auditLabels[a.status]}${a.fresh ? "" : " · versi lama"} · ${a.result.model || a.result.message || ""}`,
        "muted",
      ),
    );
  if (!view.audits.length)
    $("proposal-history").append(
      el("p", "Belum ada audit tersimpan.", "muted"),
    );
}
async function runProposalAudit(mode) {
  const id = state.document?.id;
  if (!id) return;
  lock(true);
  $("proposal-progress").textContent =
    mode === "ai"
      ? "Mengaudit 10 kriteria dan mencocokkan kutipan sumber…"
      : "Memeriksa keterbacaan dan calon heading…";
  try {
    const result = await api(
      `/api/documents/${id}/proposal/audits`,
      jsonPost({
        mode,
        guideline_ids: selectedGuidelines(),
        consent: $("proposal-consent").checked,
      }),
    );
    await refreshDashboard();
    await loadProposal(id);
    $("proposal-progress").textContent =
      mode === "structure"
        ? "Pemeriksaan struktur tersimpan. Audit isi belum dilakukan."
        : "Draf audit tersimpan. Temuan revisi masuk ke daftar tindak lanjut.";
    message(auditLabels[result.status] + " tersimpan.");
  } catch (error) {
    $("proposal-progress").textContent = error.message;
    try {
      await loadProposal(id);
    } catch {}
  } finally {
    lock(false);
  }
}
$("structure-audit").addEventListener("click", () =>
  runProposalAudit("structure"),
);
$("proposal-ai-audit").addEventListener("click", () => runProposalAudit("ai"));
$("proposal-consent").addEventListener("change", updateProposalControls);
$("finding-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const doc = state.document;
  const evidence = [
    {
      document_id: doc.id,
      pdf_page: Number($("finding-page").value),
      quote: $("finding-quote").value,
    },
  ];
  const guide = $("finding-guideline").value;
  if (guide)
    evidence.push({
      document_id: guide,
      pdf_page: Number($("finding-guideline-page").value),
      quote: $("finding-guideline-quote").value,
    });
  const payload = {
    criterion: $("finding-criterion").value,
    severity: $("finding-severity").value,
    summary: $("finding-summary").value,
    recommendation: $("finding-recommendation").value,
    actor: $("finding-actor").value,
    evidence,
    guideline_ids: guide ? [guide] : [],
  };
  lock(true);
  try {
    await api(`/api/documents/${doc.id}/proposal/issues`, jsonPost(payload));
    $("finding-form").reset();
    await refreshDashboard();
    await loadProposal(doc.id);
    message(
      "Temuan manual tersimpan pada daftar revisi, beserta lokasi buktinya.",
    );
  } catch (error) {
    message(error.message, true);
  } finally {
    lock(false);
  }
});
function renderRevisions() {
  const list = $("revision-list");
  list.replaceChildren();
  if (!state.dashboard) {
    list.append(el("p", "Pilih proyek untuk melihat revisi.", "blank-state"));
    return;
  }
  const includeOld = $("include-old-issues").checked;
  const issues = state.dashboard.issues
    .filter((i) => includeOld || i.fresh)
    .sort(
      (a, b) =>
        ({ critical: 0, major: 1, minor: 2 })[a.details.severity] -
        { critical: 0, major: 1, minor: 2 }[b.details.severity],
    );
  if (!issues.length) {
    list.append(
      el(
        "div",
        "Belum ada temuan revisi pada proposal aktif. Ini tidak berarti proposal telah lolos audit.",
        "panel blank-state",
      ),
    );
    return;
  }
  for (const issue of issues) {
    const card = el(
      "article",
      undefined,
      "panel issue-card " + issue.details.severity,
    );
    const meta = el("div", undefined, "issue-meta");
    meta.append(
      el("span", severityLabels[issue.details.severity], "badge"),
      el("span", issueLabels[issue.status], "badge"),
      el(
        "span",
        issue.origin === "ai" ? "Temuan AI · draf" : "Temuan manual",
        "badge",
      ),
    );
    if (!issue.fresh)
      meta.append(el("span", "Sumber/versi sebelumnya", "badge"));
    card.append(
      meta,
      el("h3", issue.criterion_label),
      el("p", issue.details.summary),
      el("p", "Tindak lanjut: " + issue.details.recommendation),
    );
    if (issue.fresh) evidenceNodes(issue.details.evidence, card);
    else
      for (const e of issue.details.evidence)
        card.append(el("blockquote", e.quote));
    const history = el("details"),
      summary = el("summary", "Riwayat tindak lanjut");
    history.append(summary);
    const events = el("ol", undefined, "event-list");
    for (const event of issue.events)
      events.append(
        el(
          "li",
          `${new Date(event.created_at).toLocaleString("id-ID")} · ${event.actor} · ${issueLabels[event.status]} · ${event.note}`,
        ),
      );
    history.append(events);
    card.append(history);
    if (issue.fresh) {
      const form = el("form");
      function input(text, id, tag = "input") {
        const label = el("label", text);
        label.htmlFor = id;
        const node = el(tag);
        node.id = id;
        node.required = true;
        form.append(label, node);
        return node;
      }
      const status = input(
        "Status tindak lanjut",
        "issue-status-" + issue.id,
        "select",
      );
      for (const [value, label] of Object.entries(issueLabels)) {
        const option = el("option", label);
        option.value = value;
        status.append(option);
      }
      status.value = issue.status;
      const actor = input("Nama pencatat", "issue-actor-" + issue.id);
      actor.maxLength = 100;
      const note = input(
        "Catatan tindakan atau alasan perubahan",
        "issue-note-" + issue.id,
        "textarea",
      );
      note.maxLength = 2500;
      const button = el("button", "Simpan tindak lanjut");
      button.type = "submit";
      form.append(button);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = {
          status: status.value,
          actor: actor.value,
          note: note.value,
          expected_event_id: issue.events[0]?.id,
        };
        lock(true);
        try {
          await api(`/api/issues/${issue.id}/events`, jsonPost(payload));
          await refreshDashboard();
          message(
            "Tindak lanjut tersimpan. Temuan yang ditangani tetap perlu diaudit ulang.",
          );
        } catch (error) {
          message(error.message, true);
        } finally {
          lock(false);
        }
      });
      card.append(form);
    }
    list.append(card);
  }
}
$("include-old-issues").addEventListener("change", renderRevisions);
