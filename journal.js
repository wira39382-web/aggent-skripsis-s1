"use strict";
function renderAnalyses() {
  $("analysis-results").replaceChildren();
  $("history").replaceChildren();
  const history = state.document.analyses;
  $("history-panel").hidden = !history.length;
  for (const record of history) {
    $("history").append(
      el(
        "p",
        `${new Date(record.created_at).toLocaleString("id-ID")} · ${reviewLabels[record.review_state] || "Belum ditinjau"} · ${record.result.model || record.result.message || ""}`,
        "muted",
      ),
    );
    for (const review of record.reviews || [])
      $("history").append(
        el(
          "p",
          `${review.details.reviewer} · ${reviewLabels[review.status]} · ${new Date(review.created_at).toLocaleString("id-ID")} · ${review.details.note}`,
          "muted",
        ),
      );
  }
  const record = history.find((r) => r.status === "needs_review");
  if (!record) {
    $("analysis-results").append(el("p", "Belum ada hasil analisis.", "muted"));
    return;
  }
  const result = record.result;
  $("analysis-results").append(el("p", result.message, "notice"));
  $("analysis-results").append(
    el(
      "p",
      `Model: ${result.model} · ${new Date(record.created_at).toLocaleString("id-ID")} · ${result.read_pages.length} halaman terbaca`,
      "muted",
    ),
  );
  if (result.unread_pages.length)
    $("analysis-results").append(
      el(
        "p",
        `Cakupan parsial. Halaman tidak terbaca: ${result.unread_pages.join(", ")}. “Tidak ditemukan” hanya berlaku pada teks yang terbaca.`,
        "notice",
      ),
    );
  for (const [key, label] of Object.entries(fieldLabels)) {
    const field = result.fields[key],
      card = el("div", undefined, "analysis-card");
    card.append(el("h3", label));
    if (field.status === "not_found")
      card.append(
        el(
          "p",
          "Tidak ditemukan pada teks yang terbaca. Periksa sumber asli; ini bukan bukti bahwa informasi tersebut tidak ada.",
          "not-found",
        ),
      );
    for (const claim of field.claims) {
      card.append(el("p", claim.text));
      for (const evidence of claim.evidence) {
        card.append(el("blockquote", evidence.quote));
        if (record.review_state === "stale") {
          card.append(
            el(
              "small",
              `Bukti versi lama · halaman PDF ${evidence.pdf_page}. Analisis ulang sebelum memakai bukti pada versi saat ini.`,
            ),
          );
          continue;
        }
        const button = el(
          "button",
          `Lihat bukti · halaman PDF ${evidence.pdf_page}`,
          "evidence-link",
        );
        button.type = "button";
        button.addEventListener("click", () =>
          showPage(evidence.pdf_page, evidence.quote),
        );
        card.append(button);
      }
    }
    $("analysis-results").append(card);
  }
  renderReview(record);
}
function renderReview(record) {
  const section = el("div", undefined, "review-panel");
  section.append(el("h4", "Tinjauan bukti oleh pengguna"));
  section.append(
    el("p", reviewLabels[record.review_state] || "Belum ditinjau", "notice"),
  );
  section.append(
    el(
      "small",
      "Catatan ini bukan persetujuan pembimbing atau verifikasi identitas. Periksa seluruh klaim, konteks, dan halaman sumber sebelum mencatat keputusan.",
    ),
  );
  $("analysis-results").append(section);
  if (record.review_state === "stale" || record.review_state === "superseded")
    return;
  const previous = record.reviews?.[0]?.details;
  const form = el("form");
  form.id = "human-review-form";
  function input(labelText, id, tag = "input") {
    const label = el("label", labelText);
    label.htmlFor = id;
    const node = el(tag);
    node.id = id;
    node.required = true;
    form.append(label, node);
    return node;
  }
  const reviewer = input("Nama peninjau (catatan lokal)", "reviewer");
  reviewer.maxLength = 100;
  reviewer.value = previous?.reviewer || "";
  const decisions = {};
  for (const [key, label] of Object.entries(fieldLabels)) {
    const select = input(`Tinjauan ${label}`, "review-" + key, "select");
    decisions[key] = select;
    const found = record.result.fields[key].status === "found";
    for (const [value, text] of [
      ["unknown", "Belum dapat dinilai"],
      ["needs_revision", "Perlu revisi"],
      [
        found ? "supported" : "not_found_in_readable_text",
        found
          ? "Seluruh klaim bagian ini didukung bukti"
          : "Tidak ditemukan pada teks terbaca; cakupan diperiksa",
      ],
    ]) {
      const option = el("option", text);
      option.value = value;
      select.append(option);
    }
    select.value = previous?.decisions[key] || "unknown";
  }
  const note = input("Alasan dan batas tinjauan", "review-note", "textarea");
  note.maxLength = 2000;
  const button = el("button", "Simpan catatan tinjauan");
  button.type = "submit";
  form.append(button);
  section.append(form);
  const documentId = state.document.id;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      analysis_id: record.id,
      source_sha256: record.result.source_sha256,
      extraction_sha256: record.result.extraction_sha256,
      reviewer: reviewer.value,
      note: note.value,
      decisions: Object.fromEntries(
        Object.entries(decisions).map(([key, node]) => [key, node.value]),
      ),
    };
    lock(true);
    try {
      await api(`/api/documents/${documentId}/reviews`, jsonPost(payload));
      state.document = await api(`/api/documents/${documentId}`);
      renderAnalyses();
      message("Tinjauan tersimpan untuk versi analisis ini.");
    } catch (error) {
      message(error.message, true);
    } finally {
      lock(false);
    }
  });
}
$("consent").addEventListener("change", updateAnalyze);
$("analyze").addEventListener("click", async () => {
  lock(true);
  $("analysis-progress").textContent = "Menganalisis dan memeriksa kutipan…";
  try {
    await api(
      `/api/documents/${state.document.id}/analyze`,
      jsonPost({ consent: true }),
    );
    state.document = await api(`/api/documents/${state.document.id}`);
    renderAnalyses();
    $("analysis-progress").textContent =
      "Analisis tersimpan sebagai draf. Tinjau setiap klaim dengan sumbernya.";
  } catch (e) {
    $("analysis-progress").textContent = e.message;
    try {
      state.document = await api(`/api/documents/${state.document.id}`);
      renderAnalyses();
    } catch {
      /* Keep the prior visible result. */
    }
  } finally {
    lock(false);
  }
});
