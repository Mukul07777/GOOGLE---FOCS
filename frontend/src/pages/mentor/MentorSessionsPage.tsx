import { PageHeader } from "@/components/common";
import { HostSessions } from "@/components/GroupSessions";
import { ApprovedOnly } from "@/components/MentorShell";

/** The mentor's master sessions: post them at their own price, see who registered and their doubts, mark them held. */
export default function MentorSessionsPage() {
  return (
    <ApprovedOnly>
      <div className="mx-auto max-w-4xl">
        <PageHeader eyebrow="Master sessions" title="Teach many at once"
          subtitle="Students preparing for your exam register for a seat and write the doubt they want answered, so you walk in with a queue. Everyone joins one video room; it opens ten minutes before." />
        <HostSessions />
      </div>
    </ApprovedOnly>
  );
}
