/** AIR-566–569: Client-side unified communication timeline (no API changes). */

import type { CandidateInteraction, CommunicationMessage } from "@/lib/api/candidates";

export type TimelineEventType =
  | "email"
  | "whatsapp"
  | "interview"
  | "note"
  | "stage_change"
  | "call"
  | "meeting"
  | "reply"
  | "profile"
  | "system";

export type TimelineEventTypeFilter =
  | "all"
  | "note"
  | "email"
  | "whatsapp"
  | "stage_change"
  | "interview"
  | "call"
  | "meeting";

export type TimelineDateFilter = "all" | "today" | "7d" | "30d";

export type TimelineChannelFilter = "all" | "email" | "whatsapp";

export type TimelineMessageStatusFilter =
  | "all"
  | "draft"
  | "queued"
  | "sent"
  | "delivered"
  | "read"
  | "replied"
  | "failed";

export type UnifiedTimelineEvent = {
  id: string;
  type: TimelineEventType;
  title: string;
  subtitle?: string;
  content?: string;
  status?: string;
  timestamp: Date;
  actorLabel?: string;
  relatedJobId?: string;
  relatedInterviewId?: string;
  relatedPipelineId?: string;
  metadata?: CandidateInteraction | CommunicationMessage;
};

export type BuildTimelineOptions = {
  interactions: CandidateInteraction[];
  messages: CommunicationMessage[];
  candidateEmail?: string | null;
  actorNameByUserId?: Record<string, string>;
  eventTypeFilter: TimelineEventTypeFilter;
  channelFilter: TimelineChannelFilter;
  messageStatusFilter: TimelineMessageStatusFilter;
  dateFilter: TimelineDateFilter;
  /** When false, note interactions with metadata.hidden are omitted (matches Notes tab). */
  includeHiddenNotes?: boolean;
};

/** AIR-573: shared send/delivery status labels for timeline + message lists */
export function getMessageStatusBadgeClass(status: string): string {
  switch (status) {
    case "sent":
      return "bg-green-100 text-green-700";
    case "delivered":
      return "bg-emerald-100 text-emerald-700";
    case "read":
      return "bg-emerald-100 text-emerald-800";
    case "replied":
      return "bg-blue-100 text-blue-700";
    case "failed":
      return "bg-red-100 text-red-700";
    case "queued":
      return "bg-amber-100 text-amber-800";
    case "draft":
      return "bg-gray-100 text-gray-600";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

function channelLabel(channel: CommunicationMessage["channel"]): string {
  return channel === "whatsapp" ? "WhatsApp" : "Email";
}

export function getMessageTimelineTitle(msg: CommunicationMessage): string {
  if (msg.status === "replied") {
    return `Candidate replied (${msg.channel})`;
  }
  if (msg.channel === "email" && msg.subject?.startsWith("Application update:")) {
    if (msg.status === "failed") return "Automated email failed to send";
    if (msg.status === "queued") return "Automated email queued";
    return "Automated email sent";
  }
  const label = channelLabel(msg.channel);
  switch (msg.status) {
    case "draft":
      return `${label} draft`;
    case "queued":
      return `${label} queued`;
    case "sent":
      return `${label} sent`;
    case "failed":
      return `${label} failed to send`;
    case "delivered":
      return `${label} delivered`;
    case "read":
      return `${label} read`;
    default:
      return `${label} (${msg.status})`;
  }
}

function truncateFailureReason(reason: string, maxLen = 160): string {
  const trimmed = reason.trim();
  if (trimmed.length <= maxLen) return trimmed;
  return `${trimmed.slice(0, maxLen - 1)}…`;
}

export function getMessageTimelineSubtitle(
  msg: CommunicationMessage,
  candidateEmail?: string | null
): string | undefined {
  if (msg.status === "replied") {
    return msg.subject ? `Re: ${msg.subject}` : undefined;
  }

  const parts: string[] = [];
  if (msg.channel === "whatsapp") {
    if (msg.body) parts.push(msg.body);
  } else if (msg.subject) {
    parts.push(`Subject: ${msg.subject}`);
  } else {
    const to = msg.to_address || candidateEmail;
    if (to) parts.push(`To: ${to}`);
  }
  if (msg.status === "failed" && msg.failure_reason) {
    parts.push(`Error: ${truncateFailureReason(msg.failure_reason)}`);
  }
  return parts.length > 0 ? parts.join("\n") : undefined;
}

function interactionEventType(inter: CandidateInteraction): TimelineEventType {
  const t = inter.interaction_type;
  if (t === "note") return "note";
  if (t === "interview") return "interview";
  if (t === "call") return "call";
  if (t === "meeting") return "meeting";
  if (t === "stage_change") return "stage_change";
  if (t === "email") {
    const channel = inter.metadata?.channel;
    if (channel === "whatsapp") return "whatsapp";
    return "email";
  }
  if (t === "system") return "system";
  if (inter.title?.toLowerCase().includes("profile added")) return "profile";
  return "system";
}

function metaString(meta: Record<string, unknown> | null | undefined, key: string): string | undefined {
  const v = meta?.[key];
  return typeof v === "string" && v.trim() ? v : undefined;
}

function passesDateFilter(ts: Date, dateFilter: TimelineDateFilter): boolean {
  if (dateFilter === "all") return true;
  const now = new Date();
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  if (dateFilter === "today") {
    return ts.toDateString() === start.toDateString();
  }
  const days = dateFilter === "7d" ? 7 : 30;
  const cutoff = new Date(start);
  cutoff.setDate(cutoff.getDate() - days);
  return ts >= cutoff;
}

function passesEventTypeFilter(type: TimelineEventType, filter: TimelineEventTypeFilter): boolean {
  if (filter === "all") return true;
  if (filter === "email") return type === "email" || type === "reply";
  if (filter === "whatsapp") return type === "whatsapp";
  return type === filter;
}

export function buildUnifiedTimelineEvents(options: BuildTimelineOptions): UnifiedTimelineEvent[] {
  const {
    interactions,
    messages,
    candidateEmail,
    actorNameByUserId = {},
    eventTypeFilter,
    channelFilter,
    messageStatusFilter,
    dateFilter,
    includeHiddenNotes = true,
  } = options;

  const messageIds = new Set(messages.map((m) => m.id));
  const events: UnifiedTimelineEvent[] = [];

  for (const msg of messages) {
    if (channelFilter !== "all" && msg.channel !== channelFilter) continue;
    if (messageStatusFilter !== "all" && msg.status !== messageStatusFilter) continue;

    const isReply = msg.status === "replied";
    const type: TimelineEventType = isReply ? "reply" : msg.channel === "whatsapp" ? "whatsapp" : "email";
    if (!passesEventTypeFilter(type, eventTypeFilter)) continue;

    const ts = new Date(msg.created_at);
    if (!passesDateFilter(ts, dateFilter)) continue;

    events.push({
      id: `msg-${msg.id}`,
      type,
      title: getMessageTimelineTitle(msg),
      subtitle: getMessageTimelineSubtitle(msg, candidateEmail),
      status: msg.status,
      timestamp: ts,
      metadata: msg,
    });
  }

  for (const inter of interactions) {
    if (
      !includeHiddenNotes &&
      inter.interaction_type === "note" &&
      inter.metadata &&
      inter.metadata.hidden === true
    ) {
      continue;
    }

    const linkedMessageId = metaString(inter.metadata, "message_id");
    if (linkedMessageId && messageIds.has(linkedMessageId)) {
      continue;
    }

    const type = interactionEventType(inter);
    if (!passesEventTypeFilter(type, eventTypeFilter)) continue;
    if (
      channelFilter === "email" &&
      type !== "email" &&
      type !== "reply" &&
      type !== "note" &&
      type !== "call" &&
      type !== "meeting"
    ) {
      continue;
    }
    if (
      channelFilter === "whatsapp" &&
      type !== "whatsapp" &&
      type !== "note" &&
      type !== "call" &&
      type !== "meeting"
    ) {
      continue;
    }

    const ts = new Date(inter.created_at);
    if (!passesDateFilter(ts, dateFilter)) continue;

    let subtitle = inter.body ?? undefined;
    let content: string | undefined;
    const durationMinutes = inter.metadata?.duration_minutes;
    if ((type === "call" || type === "meeting") && typeof durationMinutes === "number" && durationMinutes > 0) {
      const durationNote = `${durationMinutes} min`;
      subtitle = subtitle ? `${subtitle} · ${durationNote}` : durationNote;
    }

    if (type === "interview") {
      const scheduled = inter.metadata?.scheduled_at;
      if (typeof scheduled === "string") {
        const d = new Date(scheduled);
        content =
          d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" }) +
          ", " +
          d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
      }
      if (inter.metadata?.interview_type) {
        subtitle = `${String(inter.metadata.interview_type)} round`;
      }
    }

    const actorLabel =
      (inter.actor_user_id && actorNameByUserId[inter.actor_user_id]) ||
      inter.actor_role ||
      undefined;

    events.push({
      id: `inter-${inter.id}`,
      type,
      title: inter.title || (type === "call" ? "Phone call" : type === "meeting" ? "Meeting" : ""),
      subtitle,
      content,
      timestamp: ts,
      actorLabel,
      relatedJobId: metaString(inter.metadata, "job_id"),
      relatedInterviewId: metaString(inter.metadata, "interview_id"),
      relatedPipelineId: metaString(inter.metadata, "pipeline_id"),
      metadata: inter,
    });
  }

  events.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  return events;
}

export function groupTimelineByDate(events: UnifiedTimelineEvent[]): Record<string, UnifiedTimelineEvent[]> {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  return events.reduce<Record<string, UnifiedTimelineEvent[]>>((acc, event) => {
    const d = event.timestamp;
    let key: string;
    if (d.toDateString() === today.toDateString()) {
      key = "Today";
    } else if (d.toDateString() === yesterday.toDateString()) {
      key = "Yesterday";
    } else {
      key = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }
    acc[key] = acc[key] || [];
    acc[key].push(event);
    return acc;
  }, {});
}

export function summarizeTimelineEvents(events: UnifiedTimelineEvent[]) {
  let emails = 0;
  let whatsapp = 0;
  let replies = 0;
  for (const e of events) {
    if (e.type === "email") emails += 1;
    if (e.type === "whatsapp") whatsapp += 1;
    if (e.type === "reply") replies += 1;
  }
  return { total: events.length, emails, whatsapp, replies };
}
