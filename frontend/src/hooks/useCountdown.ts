// Lightweight tick-down hook. Returns remaining seconds; auto-stops at 0.

import { useEffect, useRef, useState } from "react";

export function useCountdown(initialSeconds: number) {
  const [seconds, setSeconds] = useState(initialSeconds);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (seconds <= 0) return;
    timer.current = setInterval(() => {
      setSeconds((s) => {
        if (s <= 1) {
          if (timer.current) clearInterval(timer.current);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reset = (n: number) => {
    if (timer.current) clearInterval(timer.current);
    setSeconds(n);
    if (n > 0) {
      timer.current = setInterval(() => {
        setSeconds((s) => {
          if (s <= 1) {
            if (timer.current) clearInterval(timer.current);
            return 0;
          }
          return s - 1;
        });
      }, 1000);
    }
  };

  return { seconds, reset };
}
