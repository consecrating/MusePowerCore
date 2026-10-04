// Shared config for capture.js and compare.js
module.exports = {
  // Fraction of differing pixels (0..1) above which a page FAILS.
  // 0.001 = 0.1% of pixels — catches real shifts, ignores rendering noise.
  failThreshold: 0.001,

  // pixelmatch options
  pixelmatchOptions: { threshold: 0.1 },

  dirs: {
    baseline: 'baselines',
    current: 'current',
    diff: 'diffs',
  },

  reportFile: 'report.html',
};
