"use client";

import type { ReactNode } from "react";
import { FileText, ExternalLink, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DocumentViewer } from "@/components/documents/DocumentViewer";
import { mimeInfoFromFileName } from "@/lib/documents/mimeTypeResolver";
import { useDocumentDownload } from "@/lib/documents/useDocumentDownload";
import { useDocumentPreview } from "@/lib/documents/useDocumentPreview";
import type { AirisDocumentInput } from "@/lib/documents/documentService";

export function DocumentCard(props: {
  heading: string;
  headingIcon?: ReactNode;
  document: AirisDocumentInput;
  hasSource: boolean;
  emptyTitle: string;
  emptyDescription?: string;
  unsupported?: boolean;
  unsupportedMessage?: string;
  extras?: ReactNode;
}) {
  const {
    heading,
    headingIcon = <FileText className="w-4 h-4 text-[#FF5A1F]" />,
    document,
    hasSource,
    emptyTitle,
    emptyDescription,
    unsupported,
    unsupportedMessage,
    extras,
  } = props;

  const fileName =
    document.flavor === "resume" ? document.resumeFileName ?? null : document.jdFileName ?? null;
  const { label } = mimeInfoFromFileName(fileName);

  const openHook = useDocumentPreview(document);
  const dlHook = useDocumentDownload(document);

  const combinedError = openHook.error || dlHook.error;
  const busy = openHook.loading || dlHook.loading;

  const displayName = fileName || (document.flavor === "resume" ? "Resume" : "Job description");

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 bg-gray-50/50 p-5">
        <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
          {headingIcon}
          {heading}
        </h2>
      </div>
      <div className="space-y-4 p-6">
        {!hasSource ? (
          <div className="rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center">
            <FileText className="mx-auto mb-2 h-8 w-8 text-gray-400" />
            <p className="text-sm font-medium text-gray-900">{emptyTitle}</p>
            {emptyDescription ? <p className="mt-1 text-xs text-gray-500">{emptyDescription}</p> : null}
          </div>
        ) : unsupported ? (
          <DocumentViewer
            fileTitle={displayName}
            fileSubtitle={label}
            icon={<FileText className="h-6 w-6" />}
            loading={busy}
            error={combinedError}
            helper={<p>{unsupportedMessage || "Preview is not available for this file type."}</p>}
          />
        ) : (
          <>
            <DocumentViewer
              fileTitle={displayName}
              fileSubtitle={label}
              icon={<FileText className="h-6 w-6" />}
              loading={busy}
              error={combinedError}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1 border-gray-200 hover:bg-gray-50 hover:text-gray-900 sm:flex-none"
                disabled={busy}
                onClick={() => {
                  openHook.clearError();
                  dlHook.clearError();
                  void openHook.preview();
                }}
              >
                <ExternalLink className="mr-2 h-4 w-4" /> Open
              </Button>
              <Button
                type="button"
                className="flex-1 bg-slate-900 text-white hover:bg-slate-800 sm:flex-none"
                disabled={busy}
                onClick={() => {
                  openHook.clearError();
                  dlHook.clearError();
                  void dlHook.download();
                }}
              >
                <Download className="mr-2 h-4 w-4" /> Download
              </Button>
            </div>
          </>
        )}

        {extras ? <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 pt-4">{extras}</div> : null}
      </div>
    </div>
  );
}
