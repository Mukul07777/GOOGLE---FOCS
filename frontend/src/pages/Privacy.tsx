import { LegalPage } from "@/components/LegalPage";
import { contactLine, SITE } from "@/lib/site";

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy"
      intro={<>{SITE.legalName} (“Focs”, “we”) helps students turn lectures into notes and practice, and connects them with mentors.
        This policy explains what we collect, why, who helps us process it, and the rights you have under India's Digital Personal
        Data Protection Act, 2023.</>}>
      <section>
        <h2>What we collect</h2>
        <ul>
          <li><b>Account details</b> — your name, email, the exam you're preparing for, your class or your college, branch and
            semester, and your language. If you sign up with a password, we store it only as a one-way hash. If you use
            <b> Continue with Google</b>, Google tells us your name and verified email address; we don't get your Google password,
            contacts or anything else in your Google account.</li>
          <li><b>Lecture boards</b> — when you share a lecture tab, Focs looks at it on your own device and sends a frame only when the
            board region you chose has changed. We keep the text read from the board, the notes written from it and a snapshot of the board.</li>
          <li><b>What the teacher says</b> — if the lecture tab's sound is shared, Focs sends pieces of about 25 seconds that contain speech
            (silence never leaves your device) to be turned into text. The audio is transcribed and then discarded: we keep only the text,
            as captions and notes. Ask your teacher before recording a live class.</li>
          <li><b>Photos you upload</b> — a photographed question, a classroom board, a handwritten answer to be marked, or a test
            result to find your weak topics. We keep what is needed to show you the answer later.</li>
          <li><b>Your study activity</b> — notes, revision sheets, flashcards and reviews, questions you answer, doubts you ask, mock
            tests, your study plan, study-room messages, and questions and answers in Ask a senior.</li>
          <li><b>If you verify a college email</b> (Ask a senior) — that address, so your answers can show your college.</li>
          <li><b>If you're a mentor</b> — what you cleared, your qualification, college or company, experience, phone number, call
            prices, profile photo, your proof document, and what Focs has paid you. Your phone number is seen only by the Focs team,
            never by students, and the proof document is deleted once we have reviewed it. Messages between mentors and students
            are kept so either side can report one; the Focs team reads a conversation only when it has been reported.</li>
          <li><b>Usage data</b> — how much of your AI allowance you've used, and basic technical logs (time, request path, response
            time, IP address) to keep the service running and protect it from abuse.</li>
        </ul>
        <p className="mt-2">We don't collect your screen outside the tab you choose, your browsing history, contacts or location. We
          don't show advertising, we don't use advertising or tracking cookies, and we never sell personal data. Your sign-in is kept
          in your browser's local storage so you stay signed in.</p>
      </section>
      <section>
        <h2>Why we use it</h2>
        <ul>
          <li>To provide Focs: read boards, write notes, answer doubts, build quizzes, mock tests, plans, analytics, study rooms,
            Ask a senior and mentor calls.</li>
          <li>To meter usage limits fairly across plans and to protect the service from abuse.</li>
          <li>To fix problems and improve quality — for example, questions students report as wrong are removed from new papers.</li>
          <li>To send you emails you need: your sign-in code, a password reset or a college-email code. We don't send marketing emails.</li>
        </ul>
      </section>
      <section>
        <h2>Who sees it</h2>
        <ul>
          <li><b>Other students</b> see only what you choose to share: your first name and initial on a leaderboard (for example
            “Riya S.”; you can hide it in Settings), your messages in a study room you join, and your answers in Ask a senior.</li>
          <li><b>A teacher whose class you join</b> sees your progress in that class: your activity, quiz results and the boards
            the class found confusing. Leaving the class stops this.</li>
          <li><b>A parent or guardian</b> you give a parent link to sees a read-only summary of your progress. You can stop sharing
            at any time.</li>
          <li><b>A mentor</b> you ask for help sees your name, your exam and what you write to them, and the doubt you add when you
            book a call or a seat.</li>
        </ul>
      </section>
      <section>
        <h2>Who helps us process it</h2>
        <ul>
          <li><b>AI providers</b> (currently Groq and Google Gemini) receive the board image or text, notes, lecture audio pieces,
            photo or question needed for each AI feature, and send back the answer. They act as our processors; we don't send your
            email or password.</li>
          <li><b>Amazon Web Services</b> runs our servers, in Mumbai, India.</li>
          <li><b>Supabase</b> hosts our database and board snapshots. Its servers are currently in Japan, so your data is stored
            outside India; we may move it to India later.</li>
          <li><b>Google</b> handles Continue with Google sign-in.</li>
          <li><b>Sentry</b> receives error reports when something breaks in the app or on our server, so we can fix it. They contain
            technical details of the error, not your name, email or study content.</li>
          <li><b>GoDaddy</b> sends our emails (sign-in codes, password resets and verification codes).</li>
          <li><b>Jitsi</b> runs the video for mentor calls and master sessions. We don't record calls.</li>
          <li><b>YouTube</b> videos in study rooms are embedded players, so YouTube's own privacy policy applies to them.</li>
          <li><b>Razorpay</b> will handle payments when paid plans launch; Focs never sees or stores your card, UPI or bank details.</li>
        </ul>
      </section>
      <section>
        <h2>Students under 18</h2>
        <p>Many of our users are school students. If you're under 18, you may use Focs only with the consent of a parent or legal
          guardian, who confirms it when the account is created. We don't show advertising and don't track children for marketing.
          Mentors can't see a student's phone number or email, and sharing contact details in mentor chats isn't allowed.
          A parent or guardian can ask us to see or delete their child's data at any time.</p>
      </section>
      <section>
        <h2>How long we keep it</h2>
        <p>We keep your data while your account is open. When you delete your account, your notes, snapshots, flashcards, answers,
          mock tests, plans and rooms you host are deleted immediately from our live systems; backups expire within 30 days. A mentor's
          payment records are kept as long as tax law requires. Technical logs and error reports are kept for up to 90 days.</p>
      </section>
      <section>
        <h2>Your rights</h2>
        <ul>
          <li><b>Access and portability</b> — Settings → Your data → Download gives you everything in one file.</li>
          <li><b>Correction</b> — edit your profile and any note directly in the app.</li>
          <li><b>Erasure</b> — Settings → Your data → Delete account removes everything.</li>
          <li><b>Withdraw consent</b> — deleting your account withdraws it; you can also hide yourself from leaderboards in Settings.</li>
          <li><b>Help and privacy requests</b> — {contactLine} for anything about your account or your data.</li>
          <li><b>Grievances</b> — {contactLine}{SITE.grievanceOfficer ? ` (Grievance Officer: ${SITE.grievanceOfficer})` : ""}. We reply within
            7 days and resolve within 30. You may also approach the Data Protection Board of India.</li>
        </ul>
      </section>
      <section>
        <h2>Security</h2>
        <p>Passwords are hashed with bcrypt, and signing in with a password also needs a one-time code sent to your email (two-step
          verification), so a leaked password alone doesn't open your account. All traffic is encrypted in transit (HTTPS), each account can reach only its own data,
          and access to production data is limited to the people who run Focs. No system is perfectly secure; if a breach affects
          you, we will tell you and the authorities as the law requires.</p>
      </section>
      <section>
        <h2>Changes</h2>
        <p>If we change this policy in a way that matters, we'll tell you in the app before it takes effect.</p>
      </section>
    </LegalPage>
  );
}
