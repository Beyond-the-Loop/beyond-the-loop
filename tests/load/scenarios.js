export const smoke = {
  executor: 'constant-vus',
  vus: 1,
  duration: '1m',
};

export const baseline = {
  executor: 'ramping-vus',
  startVUs: 1,
  stages: [
    { duration: '30s', target: 5 },
    { duration: '3m', target: 10 },
    { duration: '30s', target: 0 },
  ],
  gracefulRampDown: '30s',
};

export const stress = {
  executor: 'ramping-vus',
  startVUs: 1,
  stages: [
    { duration: '1m', target: 20 },
    { duration: '3m', target: 50 },
    { duration: '3m', target: 100 },
    { duration: '3m', target: 200 },
    { duration: '1m', target: 0 },
  ],
  gracefulRampDown: '1m',
};

export const spike = {
  executor: 'ramping-vus',
  startVUs: 1,
  stages: [
    { duration: '10s', target: 100 },
    { duration: '30s', target: 100 },
    { duration: '10s', target: 0 },
  ],
  gracefulRampDown: '30s',
};

export const soak = {
  executor: 'constant-vus',
  vus: 20,
  duration: '30m',
};
