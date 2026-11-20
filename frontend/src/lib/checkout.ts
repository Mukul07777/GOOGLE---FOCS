import { api } from "@/lib/api";
import type { Checkout, User } from "@/lib/types";

type RazorpayResponse = { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string };
type RazorpayCtor = new (options: Record<string, unknown>) => { open: () => void; on: (event: string, cb: (r: unknown) => void) => void };

const SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";
let loading: Promise<void> | null = null;

function loadRazorpay(): Promise<void> {
  if ((window as unknown as { Razorpay?: RazorpayCtor }).Razorpay) return Promise.resolve();
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT;
    s.onload = () => resolve();
    s.onerror = () => { loading = null; reject(new Error("Couldn't load the payment window. Check your connection.")); };
    document.body.appendChild(s);
  });
  return loading;
}

export class PaymentCancelled extends Error {
  constructor() { super("Payment cancelled"); }
}

/** Take a payment the server has started: Razorpay's checkout (UPI, cards, netbanking), or on a dev server a test
    payment where no money moves. Resolves once the server has verified it. */
export async function pay(c: Checkout): Promise<{ status: string; purpose: string; user: User }> {
  if (c.provider === "dev") {
    if (!window.confirm(`Test payment of ₹${c.amount_inr} for ${c.description}.\n\nThis is a dev server: no money moves. Continue?`)) throw new PaymentCancelled();
    return api.confirmPayment(c.payment_id, {});
  }
  await loadRazorpay();
  const Razorpay = (window as unknown as { Razorpay: RazorpayCtor }).Razorpay;
  const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#6d5efc";
  const paid = await new Promise<RazorpayResponse>((resolve, reject) => {
    const rz = new Razorpay({
      key: c.key_id, order_id: c.order_id, amount: c.amount_paise, currency: c.currency, name: "Focs", description: c.description,
      prefill: c.prefill, theme: { color: accent.startsWith("#") ? accent : "#6d5efc" },
      handler: (r: RazorpayResponse) => resolve(r),
      modal: { ondismiss: () => reject(new PaymentCancelled()) },
    });
    rz.on("payment.failed", () => reject(new Error("The payment didn't go through. No money was taken; try again or use another method.")));
    rz.open();
  });
  return api.confirmPayment(c.payment_id, paid);
}
