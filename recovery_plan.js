/* Local presentation state only. The server revalidates every execution. */
'use strict';
class RecoveryPlan {
  static labels = {'1':'Synthetic ticket opened','2':'Synthetic ticket assigned','3':'Synthetic ticket resolved'};
  constructor() { this.invalidate(); }
  invalidate() { this.observation = null; this.count = 0; this.plan = null; }
  observe(report) {
    this.invalidate();
    const ids = Object.keys(RecoveryPlan.labels), allowed = report?.allowed;
    if (report?.blocked !== false || report.cancelled !== false ||
        !/^[a-f0-9]{64}$/.test(report.preview || '') ||
        typeof report.run !== 'string' || !Number.isSafeInteger(report.version) || report.version < 0 ||
        !Array.isArray(allowed) || !allowed.length || allowed.length > ids.length ||
        !report.statuses || Object.keys(report.statuses).length !== ids.length) return;
    const expected = ids.slice(ids.length - allowed.length);
    if (allowed.some((id, index) => id !== expected[index]) ||
        ids.some(id => report.statuses[id] !== (allowed.includes(id) ? 'MISSING' : 'VERIFIED'))) return;
    this.observation = {preview:report.preview, run:report.run, version:report.version, allowed:[...allowed]};
    this.count = 1; // Smallest next step; execution still requires explicit review.
  }
  get choices() {
    return this.observation ? this.observation.allowed.map((id, index) => ({count:index+1,label:RecoveryPlan.labels[id]})) : [];
  }
  get canPrepare() { return this.observation !== null && this.count > 0; }
  get prepared() { return this.plan ? {...this.plan, effects:[...this.plan.effects]} : null; }
  choose(count) {
    this.plan = null;
    this.count = 0;
    if (!this.observation || !Number.isInteger(count) || count < 1 || count > this.observation.allowed.length) return;
    this.count = count;
  }
  prepare() {
    if (!this.canPrepare) return null;
    this.plan = {...this.observation, effects:this.observation.allowed.slice(0,this.count)};
    delete this.plan.allowed;
    return this.prepared;
  }
  discard() { this.plan = null; }
  takeRequest() {
    if (!this.plan) return null;
    const request = {preview:this.plan.preview,effects:[...this.plan.effects]};
    this.invalidate(); // Lost acknowledgement cannot reuse an old prepared plan.
    return request;
  }
}
if (typeof module !== 'undefined' && module.exports) module.exports = RecoveryPlan;
