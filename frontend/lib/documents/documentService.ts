import { API_BASE_URL } from "@/lib/api/client";

export type ResumeDocumentInput = {
  flavor: "resume";
  candidateId: string;
  resumeS3Key: string | null | undefined;
  resumeFileName: string | null | undefined;
};

export type JobJdDocumentInput = {
  flavor: "job_jd";
  jobId: string;
  jdOriginalAvailable: boolean;
  jdFileName: string | null | undefined;
};

export type AirisDocumentInput = ResumeDocumentInput | JobJdDocumentInput;

function authHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("airis_access_token") : null;
  const orgId = typeof window !== "undefined" ? localStorage.getItem("airis_organization_id") : null;
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(orgId ? { "X-Workspace-Id": orgId } : {}),
  };
}

function resumeDownloadBase(candidateId: string) {
  return `${API_BASE_URL}/candidate-management/candidates/${candidateId}/resume`;
}

function resumePreviewUrl(candidateId: string) {
  return `${API_BASE_URL}/candidate-management/candidates/${candidateId}/resume/preview`;
}

function jdDownloadBase(jobId: string) {
  return `${API_BASE_URL}/jobs/${jobId}/jd-document`;
}

function jdPreviewUrl(jobId: string) {
  return `${API_BASE_URL}/jobs/${jobId}/jd-document/preview`;
}

function isExternalResumeUrl(keyOrUrl: string | null | undefined): boolean {
  if (!keyOrUrl) return false;
  return /^https?:\/\//.test(keyOrUrl) && !keyOrUrl.includes("/candidate-management/");
}

/**
 * Open original document in a new tab (DOCX via docx-preview, DOC via server HTML, PDF/TXT via blob inline).
 * Mirrors candidate resume behavior — no dangerouslySetInnerHTML in the app shell (DOC uses blob URL of full HTML document from trusted API).
 */
export async function openAirisDocument(input: AirisDocumentInput): Promise<void> {
  if (input.flavor === "resume") {
    const { candidateId, resumeS3Key, resumeFileName } = input;
    if (!resumeS3Key) throw new Error("No document on file.");
    const resumeUrl = isExternalResumeUrl(resumeS3Key) ? resumeS3Key : resumeDownloadBase(candidateId);
    if (isExternalResumeUrl(resumeS3Key)) {
      window.open(resumeUrl, "_blank", "noopener,noreferrer");
      return;
    }
    const fileName = (resumeFileName || "").toLowerCase();
    await openManagedDocument({
      downloadBaseUrl: resumeUrl,
      previewUrl: resumePreviewUrl(candidateId),
      dispositionFileName: resumeFileName || "resume.pdf",
      fileNameLower: fileName,
    });
    return;
  }

  const { jobId, jdOriginalAvailable, jdFileName } = input;
  if (!jdOriginalAvailable) throw new Error("No original job description file on file.");
  const fileName = (jdFileName || "").toLowerCase();
  await openManagedDocument({
    downloadBaseUrl: jdDownloadBase(jobId),
    previewUrl: jdPreviewUrl(jobId),
    dispositionFileName: jdFileName || "job-description.pdf",
    fileNameLower: fileName,
  });
}

type ManagedOpenArgs = {
  downloadBaseUrl: string;
  previewUrl: string;
  dispositionFileName: string;
  fileNameLower: string;
};

async function openManagedDocument(args: ManagedOpenArgs): Promise<void> {
  const { downloadBaseUrl, previewUrl, dispositionFileName, fileNameLower } = args;
  const isDocx = fileNameLower.endsWith(".docx");
  const isDoc = fileNameLower.endsWith(".doc");

  if (isDocx) {
    const docxUrl = `${downloadBaseUrl}${downloadBaseUrl.includes("?") ? "&" : "?"}disposition=attachment`;
    const docxRes = await fetch(docxUrl, { headers: authHeaders() });
    if (!docxRes.ok) throw new Error("Failed to load DOCX document");
    const arrayBuffer = await docxRes.arrayBuffer();
    const previewWin = window.open("", "_blank");
    if (!previewWin) throw new Error("Popup blocked. Please allow popups for document preview.");
    previewWin.document.write(
      "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>" +
        "<title>Document Preview</title>" +
        "<style>" +
        "body{margin:0;background:#f8fafc;font-family:Inter,Segoe UI,Arial,sans-serif;}" +
        ".viewer-shell{max-width:980px;margin:20px auto;padding:0 12px;}" +
        ".docx-wrapper{background:transparent;padding:0 !important;}" +
        ".docx{background:#fff !important;border:1px solid #e2e8f0;border-radius:12px;padding:28px !important;box-shadow:0 1px 2px rgba(0,0,0,.04);}" +
        "</style>" +
        "</head><body><div id='docx'></div></body></html>"
    );
    previewWin.document.close();
    const container = previewWin.document.getElementById("docx");
    if (!container) throw new Error("Failed to initialize preview container.");
    container.className = "viewer-shell";
    const { renderAsync } = await import("docx-preview");
    await renderAsync(arrayBuffer, container, previewWin.document.head, {
      className: "docx",
      inWrapper: true,
      ignoreWidth: true,
      ignoreHeight: true,
      breakPages: false,
      ignoreFonts: false,
    });
    return;
  }

  if (isDoc) {
    const previewRes = await fetch(previewUrl, { headers: authHeaders() });
    if (!previewRes.ok) throw new Error("Failed to load document preview");
    const preview = (await previewRes.json()) as { file_name: string; html: string };
    const htmlBlob = new Blob([preview.html], { type: "text/html" });
    const url = URL.createObjectURL(htmlBlob);
    window.open(url, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return;
  }

  const targetUrl = `${downloadBaseUrl}${downloadBaseUrl.includes("?") ? "&" : "?"}disposition=inline`;
  const response = await fetch(targetUrl, { headers: authHeaders() });
  if (!response.ok) throw new Error("Failed to open document");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(url), 120_000);
}

export async function downloadAirisDocument(input: AirisDocumentInput): Promise<void> {
  if (input.flavor === "resume") {
    const { candidateId, resumeS3Key, resumeFileName } = input;
    if (!resumeS3Key) throw new Error("No document on file.");
    const resumeUrl = isExternalResumeUrl(resumeS3Key) ? resumeS3Key : resumeDownloadBase(candidateId);
    if (isExternalResumeUrl(resumeS3Key)) {
      window.open(resumeUrl, "_blank", "noopener,noreferrer");
      return;
    }
    await downloadManaged(`${resumeUrl}${resumeUrl.includes("?") ? "&" : "?"}disposition=attachment`, resumeFileName || "resume.pdf");
    return;
  }
  const { jobId, jdOriginalAvailable, jdFileName } = input;
  if (!jdOriginalAvailable) throw new Error("No original job description file on file.");
  const base = jdDownloadBase(jobId);
  await downloadManaged(`${base}${base.includes("?") ? "&" : "?"}disposition=attachment`, jdFileName || "job-description.pdf");
}

async function downloadManaged(url: string, downloadName: string): Promise<void> {
  const response = await fetch(url, { headers: authHeaders() });
  if (!response.ok) throw new Error("Failed to download document");
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = downloadName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(objectUrl), 2000);
}
