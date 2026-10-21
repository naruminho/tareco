/* The time slider shown for timelines: pick a period or replay them all. The last
   position means "all periods". onChange(period or null) is called on every move. */
function tarecoTimebar(time, T, fmt, onChange) {
  "use strict";
  if (!time) return null;
  const $ = (id) => document.getElementById(id);
  const bar = $("timebar"), range = $("time-range"), label = $("time-label"), play = $("time-play");
  const P = time.periods.length;
  bar.hidden = false;
  document.body.classList.add("has-time");
  range.min = "0";
  range.max = String(P);
  range.value = String(P);
  let timer = 0;

  function render() {
    const v = Number(range.value);
    const current = v >= P ? null : v;
    label.textContent = current === null
      ? T.allPeriods
      : `${time.periods[current]} \u00b7 ${fmt(time.counts[current])} ${T.edges}`;
    onChange(current);
  }
  function stop() {
    clearInterval(timer);
    timer = 0;
    play.classList.remove("on");
    play.dataset.tip = T.play;
    play.setAttribute("aria-label", T.play);
  }
  play.dataset.tip = T.play;
  play.setAttribute("aria-label", T.play);
  play.onclick = () => {
    if (timer) return stop();
    if (Number(range.value) >= P) range.value = "0";
    render();
    play.classList.add("on");
    play.dataset.tip = T.pause;
    play.setAttribute("aria-label", T.pause);
    timer = setInterval(() => {
      const next = Number(range.value) + 1;
      range.value = String(Math.min(next, P));
      render();
      if (next >= P) stop();
    }, 1100);
  };
  range.addEventListener("input", () => { stop(); render(); });
  label.textContent = T.allPeriods;
  return {
    set(period) {
      stop();
      range.value = String(period === null || period === undefined ? P : period);
      render();
    },
  };
}
