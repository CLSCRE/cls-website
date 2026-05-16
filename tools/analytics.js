'use strict';
var Analytics = (function () {
  function push(eventName, params) {
    window.dataLayer = window.dataLayer || [];
    var payload = { event: eventName };
    if (params) {
      for (var k in params) {
        if (Object.prototype.hasOwnProperty.call(params, k)) payload[k] = params[k];
      }
    }
    window.dataLayer.push(payload);
  }
  return {
    push: push,
    calculatorInteraction: function (name) { push('calculator_interaction', { calculator_name: name }); },
    quoteRequested: function (amount, type, propVal) { push('quote_requested', { loan_amount: amount, loan_type: type, property_value: propVal }); },
    rateTableFilter: function (filterType, value) { push('rate_table_filter', { filter_type: filterType, filter_value: value }); },
    rateCtaClick: function (product, rateRange) { push('rate_cta_click', { product: product, rate_range: rateRange }); },
    refiCalcRun: function (savings, ltv) { push('refi_calc_run', { annual_savings: savings, new_ltv: ltv }); },
    refiLeadCaptured: function () { push('refi_lead_captured', {}); }
  };
})();
