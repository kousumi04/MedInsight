"use client";

import { useRef } from "react";

const sources = [
  ["Nature Medicine: Solid Tumor Microenvironment", "Nature · 2024"],
  ["Clinical Trials: NCT04433221 Phase II", "ClinicalTrials.gov · 2023"],
  ["ASCO Annual Report 2024", "ASCO · 2024"],
];

const sourceIcon =
  "https://lh3.googleusercontent.com/aida-public/AB6AXuBNQZQwyIYzzrGS3Yjq3HCA_vmL5O8uJL3Y2CaDOjpLTvpwqOn-4ughVvzzw1XNa8JpgDu0Ns4NTl9SHCy58FjWxUjgF950uBY0EUjrVPkYmaFugs9uSDl1uIOm9RQohJu8MDGUszr9Vtyipa_RFv-xnd48aVMUj7jK67IkCcDejev9xhSOX999bKW42yqwgnVTQh_G3YamtHPQ1K05ZHVGW6E9LsIq10q-k7aNZXe0FDliHwiYdBnplObMnOGJrVb4RfC_gynpA8au";

const relatedQuestions = [
  "What are the specific toxicities associated with Mesothelin-targeted CAR-T cells?",
  "Compare NK-cell therapy vs. CAR-T therapy for ovarian cancer.",
  "Latest Phase II data on GD2-directed CAR-T for neuroblastoma.",
];

function Icon({ children, className = "" }) {
  return <span className={`material-symbols-outlined ${className}`}>{children}</span>;
}

export default function PreviewPage() {
  const textareaRef = useRef(null);

  function resizeTextarea() {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
    if (textarea.scrollHeight > 200) {
      textarea.style.overflowY = "auto";
      textarea.style.height = "200px";
    } else {
      textarea.style.overflowY = "hidden";
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0A0A0A] text-on-surface">
      <main className="relative flex h-full flex-1 flex-col bg-[#0A0A0A]">
        <header className="flex h-16 items-center justify-between border-b border-outline-variant bg-[#0A0A0A] px-margin-desktop">
          <div className="flex items-center gap-4">
            <span className="font-label-caps text-label-caps text-on-surface-variant">RESEARCH THREAD</span>
            <span className="text-outline-variant">/</span>
            <span className="font-body-md text-body-md font-semibold">
              Latest advancements in CAR-T therapy for solid tumors
            </span>
          </div>
          <button className="flex items-center gap-2 rounded border border-outline-variant px-3 py-1.5 text-on-surface-variant transition-colors hover:border-primary hover:text-primary">
            <Icon className="text-[18px]">share</Icon>
            <span className="font-label-caps text-label-caps">SHARE</span>
          </button>
        </header>

        <div className="custom-scrollbar flex-1 overflow-y-auto pb-40 pt-8">
          <div className="mx-auto max-w-4xl space-y-12 px-6">
            <section className="flex gap-6">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded border border-outline-variant bg-surface-container">
                <Icon className="text-[20px] text-on-surface-variant">person</Icon>
              </div>
              <h2 className="mb-2 font-headline-lg text-headline-lg">
                Can you summarize the current challenges and recent breakthroughs in applying CAR-T therapy to
                solid tumors?
              </h2>
            </section>

            <section className="flex gap-6">
              <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded bg-primary-container">
                <Icon
                  className="text-[20px] text-on-primary-container"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  bolt
                </Icon>
              </div>

              <div className="flex-1 space-y-8">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-on-surface-variant">
                    <Icon className="text-[18px]">source</Icon>
                    <span className="font-label-caps text-label-caps">SOURCES</span>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    {sources.map(([title, meta]) => (
                      <a
                        key={title}
                        className="block rounded-lg border border-outline-variant bg-[#141414] p-3 transition-colors hover:border-primary"
                        href="#"
                      >
                        <p className="mb-1 line-clamp-1 font-body-sm text-body-sm font-semibold">{title}</p>
                        <div className="flex items-center gap-2">
                          <img alt="" className="h-3 w-3 opacity-60 grayscale" src={sourceIcon} />
                          <span className="text-[10px] text-on-surface-variant">{meta}</span>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>

                <div className="max-w-none space-y-4">
                  <p className="font-body-md text-body-md leading-relaxed text-on-surface">
                    While CAR-T cell therapy has achieved remarkable success in hematologic malignancies, its
                    application to solid tumors remains hindered by three primary barriers:{" "}
                    <span className="font-semibold text-primary">antigen heterogeneity</span>,{" "}
                    <span className="font-semibold text-primary">poor trafficking</span>, and the{" "}
                    <span className="font-semibold text-primary">immunosuppressive tumor microenvironment (TME)</span>.
                  </p>

                  <div className="space-y-4 rounded-r-lg border-l-2 border-primary bg-[#141414] p-6">
                    <h3 className="font-headline-md text-headline-md text-primary">
                      Key Breakthroughs (2023-2024)
                    </h3>
                    <ul className="space-y-3 font-body-sm text-body-sm">
                      {[
                        [
                          "Armored CARs:",
                          "New constructs engineered to secrete IL-12 or IL-15 are showing promise in remodeling the TME, allowing better T-cell persistence in pancreatic ductal adenocarcinoma [1].",
                        ],
                        [
                          "Dual-Antigen Targeting:",
                          'Logic-gated CARs (AND/OR gates) are being deployed to mitigate "off-tumor" toxicity by requiring two specific markers before activation [2].',
                        ],
                        [
                          "Regional Delivery:",
                          "Intratumoral or intracavitary delivery methods are proving more effective for glioblastoma than systemic intravenous injection [3].",
                        ],
                      ].map(([heading, body], index) => (
                        <li key={heading} className="flex gap-3">
                          <span className="font-bold text-primary">{String(index + 1).padStart(2, "0")}</span>
                          <span>
                            <strong className="text-on-surface">{heading}</strong> {body}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <p className="font-body-md text-body-md leading-relaxed text-on-surface">
                    Recent Phase I/II results suggest that combining CAR-T with immune checkpoint inhibitors (e.g.,
                    PD-1 blockade) significantly improves objective response rates (ORR) in refractory patients.
                    However, the risk of cytokine release syndrome (CRS) remains a critical monitoring parameter.
                  </p>
                </div>

                <div className="flex flex-col justify-between gap-6 border-t border-outline-variant pt-6 md:flex-row md:items-center">
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                      <span className="font-label-caps text-label-caps text-on-surface-variant">AI CONFIDENCE</span>
                      <div className="flex gap-1">
                        {[0, 1, 2, 3, 4].map((item) => (
                          <div
                            key={item}
                            className={`h-1 w-3 rounded-full ${item < 4 ? "bg-primary" : "bg-outline-variant"}`}
                          />
                        ))}
                      </div>
                      <span className="text-[10px] font-bold text-primary">88%</span>
                    </div>
                    <div className="h-4 w-px bg-outline-variant" />
                    <div className="flex items-center gap-4 text-on-surface-variant">
                      {[
                        ["content_copy", "COPY"],
                        ["download", "EXPORT"],
                      ].map(([icon, label]) => (
                        <button key={label} className="flex items-center gap-1 transition-colors hover:text-primary">
                          <Icon className="text-[18px]">{icon}</Icon>
                          <span className="font-label-caps text-label-caps">{label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {["thumb_up", "thumb_down"].map((icon) => (
                      <button key={icon} className="rounded border border-outline-variant p-2 transition-colors hover:border-primary">
                        <Icon className="text-on-surface-variant">{icon}</Icon>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center gap-2 text-on-surface-variant">
                    <Icon className="text-[18px]">link</Icon>
                    <span className="font-label-caps text-label-caps">RELATED</span>
                  </div>
                  <div className="space-y-2">
                    {relatedQuestions.map((question) => (
                      <button
                        key={question}
                        className="group flex w-full items-center justify-between rounded-lg border border-outline-variant bg-[#141414] p-4 text-left transition-all hover:border-primary"
                      >
                        <span className="font-body-sm text-body-sm">{question}</span>
                        <Icon className="text-on-surface-variant transition-colors group-hover:text-primary">
                          arrow_forward
                        </Icon>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div className="pointer-events-none absolute bottom-0 left-0 right-0 p-8">
          <div className="pointer-events-auto mx-auto w-full max-w-3xl">
            <div className="rounded-xl border border-outline-variant bg-[#141414] p-4 shadow-2xl transition-all focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/20">
              <div className="flex items-start gap-3">
                <textarea
                  ref={textareaRef}
                  className="custom-scrollbar w-full resize-none border-none bg-transparent py-2 font-body-md text-body-md text-on-surface placeholder:text-on-surface-variant/40 focus:ring-0"
                  onInput={resizeTextarea}
                  placeholder="Ask MedInsight clinical research questions..."
                  rows={1}
                />
                <button className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 font-bold text-on-primary transition-all hover:bg-primary-fixed-dim active:scale-95">
                  <span className="font-label-caps text-label-caps">SEARCH</span>
                  <Icon className="text-[20px]">arrow_upward</Icon>
                </button>
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-outline-variant/30 pt-3">
                <div className="flex items-center gap-2">
                  {[
                    ["target", "FOCUS: CLINICAL TRIALS"],
                    ["upload_file", "UPLOAD PDF"],
                  ].map(([icon, label]) => (
                    <button
                      key={label}
                      className="flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-1.5 text-on-surface-variant transition-colors hover:border-primary hover:text-primary"
                    >
                      <Icon className="text-[18px]">{icon}</Icon>
                      <span className="font-label-caps text-label-caps">{label}</span>
                    </button>
                  ))}
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input defaultChecked className="peer sr-only" type="checkbox" />
                  <div className="peer h-5 w-9 rounded-full bg-surface-container-high after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-primary peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:outline-none" />
                  <span className="ml-2 font-label-caps text-label-caps text-on-surface-variant">PRO MODE</span>
                </label>
              </div>
            </div>
            <p className="mt-3 text-center text-[10px] uppercase tracking-widest text-on-surface-variant/50">
              MedInsight AI utilizes verified peer-reviewed data. Verify critical clinical findings.
            </p>
          </div>
        </div>
      </main>

      <aside className="custom-scrollbar hidden w-72 flex-col space-y-8 overflow-y-auto border-l border-outline-variant bg-[#0A0A0A] p-6 lg:flex">
        <div>
          <h3 className="mb-4 font-label-caps text-label-caps tracking-widest text-on-surface-variant">KEY ENTITIES</h3>
          <div className="space-y-3">
            {[
              ["DRUG TARGET", "MSLN (Mesothelin)", "High expression in pancreatic & ovarian cancer."],
              ["BIOMARKER", "IFN-γ", "Cytokine release indicator."],
            ].map(([label, title, body]) => (
              <div key={label} className="rounded-lg border border-outline-variant bg-surface-container p-3">
                <p className="mb-1 font-label-caps text-label-caps text-primary">{label}</p>
                <p className="font-body-sm text-body-sm font-semibold">{title}</p>
                <p className="mt-1 text-[10px] text-on-surface-variant">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex-1 border-t border-outline-variant pt-6">
          <h3 className="mb-4 font-label-caps text-label-caps tracking-widest text-on-surface-variant">
            RESEARCH GRAPH
          </h3>
          <div className="group relative flex aspect-square items-center justify-center overflow-hidden rounded-lg border border-outline-variant bg-surface-container">
            <img
              alt=""
              className="h-full w-full object-cover opacity-30 grayscale transition-transform duration-700 group-hover:scale-110"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDL_CPgFpEI5yQFul9AbcnXiRfj4SdrMPWwyPg0SUqSNf2rW21aDhd1kZ1ZJg0pQXNZ6dge0tFsnJ_SQPmVhXdHSdGPUrUHPE8T3d-Sgsp4pmmRd8z9fScwgC9QPyQw47k7RwAROwns0aA7lIzHynoKSi7zYO0zdDlFsQGKXqVq2K104ugfcbEnT-sC6zfzDH7BYtTHjpWZ5cXA4rbk9SnqjH9PKu1qh5ZnUL-LkVzUcd6IcDZRMknR4RoMCFg2yqq_Pc3J1ElmsHmM"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <button className="rounded-full border border-primary bg-[#0A0A0A]/80 px-3 py-1 font-label-caps text-[10px] text-primary">
                OPEN GRAPH VIEW
              </button>
            </div>
          </div>
        </div>

        <div className="border-t border-outline-variant pt-6">
          <h3 className="mb-4 font-label-caps text-label-caps tracking-widest text-on-surface-variant">METHODOLOGY</h3>
          <p className="text-[11px] leading-relaxed text-on-surface-variant">
            Query processed using <strong>Med-7B Model</strong>. Sources indexed from PubMed (v2024), Cochrane
            Library, and bioRxiv pre-prints. Statistical significance validated via meta-analysis cross-referencing.
          </p>
        </div>
      </aside>
    </div>
  );
}
