let pending: Promise<void> | undefined;

/** One shared load per attempt; a failed or timed-out load can be retried. */
export function loadRazorpaySdk(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  if (pending) return pending;
  const attempt = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    const fail = () => {
      clearTimeout(timer);
      script.remove();
      reject(new Error('Payment checkout could not load. Check your connection and try again.'));
    };
    const timer = setTimeout(fail, 15000);
    script.onerror = fail;
    script.onload = () => {
      if (!window.Razorpay) { fail(); return; }
      clearTimeout(timer);
      resolve();
    };
    document.head.append(script);
  });
  pending = attempt;
  void attempt.catch(() => { if (pending === attempt) pending = undefined; });
  return attempt;
}
