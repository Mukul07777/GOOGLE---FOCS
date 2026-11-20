import { Link } from "react-router-dom";
import { LegalPage } from "@/components/LegalPage";
import { contactLine, SITE } from "@/lib/site";

export default function Terms() {
  return (
    <LegalPage title="Terms of Service"
      intro={<>These terms are the agreement between you and {SITE.legalName} for using Focs. By creating an account you accept them
        and our <Link to="/privacy" className="text-accent underline underline-offset-2">Privacy Policy</Link>.</>}>
      <section>
        <h2>Your account</h2>
        <ul>
          <li>You must be 18 or older, or have a parent or legal guardian's consent to use Focs.</li>
          <li>Keep your password (or the Google account you sign in with) private. You're responsible for what happens under
            your account. Signing in with a password also needs a one-time code we email you; never share that code with anyone,
            including someone saying they're from Focs.</li>
          <li>An account is a student account or a mentor account. Mentor accounts are for guiding students and can't use the
            study features.</li>
          <li>One person per account. Sharing an account or creating many accounts to get around usage limits isn't allowed.</li>
        </ul>
      </section>
      <section>
        <h2>Using Focs fairly</h2>
        <ul>
          <li>Only capture lectures you have the right to watch. Notes Focs writes are for your personal study — don't use Focs to copy
            or redistribute paid courses.</li>
          <li>Be kind in study rooms: no harassment, hate, sexual content, spam or sharing other people's personal information.
            Hosts can close rooms; we may remove content or accounts that break these rules.</li>
          <li>Don't try to break, overload, scrape or reverse-engineer the service.</li>
        </ul>
      </section>
      <section>
        <h2>About AI answers and mock tests</h2>
        <p>Notes, answers, quizzes and mock-test questions are written by AI. We check mock questions with a second, independent AI
          solution and retire questions students report, but mistakes can still happen. Focs is a study aid — check important facts
          with your teachers and textbooks. Focs mock tests follow the pattern of your exam (JEE, NEET, the CBSE boards,
          GATE or your college course) but are not official papers of the NTA, CBSE, any university or any other body, and scores
          are not a prediction of your exam result.</p>
      </section>
      <section>
        <h2>Plans, limits and payments</h2>
        <ul>
          <li>The free plan includes AI notes for half an hour of live lecture a day, a daily AI allowance for everything else
            (each refreshes a day after you start using it), a weekly cap, a weekly allowance of lecture captions, and one full
            mock test a week. Pro includes AI notes for up to seven hours of live lecture a day and raises the other limits as
            described on the pricing page. Every plan also has a 30-day fair-use limit on AI, well above what a full study day needs; past it,
            AI features give basic answers until older use drops off.</li>
          <li>Limits keep the service fair and affordable for everyone. When you run out, live lectures continue with basic notes.</li>
          <li>Pro is paid in advance for a fixed time (a month, six months or a year) and does not renew by itself: when it ends you
            return to the free plan unless you choose to pay again. If you're unhappy within 7 days of your first payment,
            {" "}{contactLine} for a full refund.</li>
          <li>Mentor calls and master-session seats are priced by each mentor and paid per booking. A booking cancelled at least
            12 hours before it starts, or cancelled by the mentor, is refunded in full.</li>
          <li>We may change prices or limits with notice in the app; changes never apply to a period you've already paid for.</li>
        </ul>
      </section>
      <section>
        <h2>Mentors</h2>
        <ul>
          <li>Mentors are independent people who have cleared an exam, not Focs employees. Focs checks each mentor's proof
            before listing them, but doesn't guarantee their advice or results.</li>
          <li>Many students are under 18. Mentors must keep every conversation and call on Focs, must not ask for or share phone
            numbers, emails or social media handles, and must not meet students outside Focs. Either side can report a
            conversation; we may remove a mentor who breaks these rules.</li>
          <li>Mentors set their own prices. Focs keeps 20% of each paid call or seat and pays the mentor the rest, after the
            booking has taken place.</li>
        </ul>
      </section>
      <section>
        <h2>Your content</h2>
        <p>Your notes and study data belong to you. You give us permission to store and process them only to run Focs for you. You can
          download or delete them at any time from Settings.</p>
      </section>
      <section>
        <h2>Ending your account</h2>
        <p>You can delete your account whenever you like. We may suspend accounts that seriously or repeatedly break these terms,
          and we'll tell you why unless the law prevents it.</p>
      </section>
      <section>
        <h2>Liability</h2>
        <p>Focs is provided “as is”. To the extent the law allows, we aren't liable for indirect losses such as exam results, and our
          total liability to you is limited to what you paid us in the 12 months before the claim. Nothing here limits rights you have
          under the Consumer Protection Act, 2019.</p>
      </section>
      <section>
        <h2>Law and disputes</h2>
        <p>These terms are governed by the laws of {SITE.jurisdiction}. Tell us about any problem first — {contactLine} — and we'll try
          to resolve it within 30 days.</p>
      </section>
    </LegalPage>
  );
}
