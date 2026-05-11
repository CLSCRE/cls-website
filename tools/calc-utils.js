'use strict';
var CalcUtils = (function () {
  function monthlyPayment(principal, annualRatePct, termMonths, interestOnly) {
    if (!principal || !annualRatePct || !termMonths) return 0;
    var r = annualRatePct / 100 / 12;
    if (interestOnly) return principal * r;
    if (r === 0) return principal / termMonths;
    return principal * (r * Math.pow(1 + r, termMonths)) / (Math.pow(1 + r, termMonths) - 1);
  }
  function dscr(annualNOI, annualDebtService) {
    if (!annualDebtService) return 0;
    return annualNOI / annualDebtService;
  }
  function maxLoan(propertyValue, ltvPct) { return propertyValue * ltvPct / 100; }
  function originationFee(loanAmount, feePct) { return loanAmount * feePct / 100; }
  function balloonBalance(principal, annualRatePct, amortMonths, termMonths) {
    if (!principal || !annualRatePct || termMonths >= amortMonths) return 0;
    var r = annualRatePct / 100 / 12;
    var pmt = monthlyPayment(principal, annualRatePct, amortMonths, false);
    var bal = principal;
    for (var m = 0; m < termMonths; m++) { bal = bal * (1 + r) - pmt; }
    return Math.max(0, bal);
  }
  function breakeven(closingCosts, monthlySavings) {
    if (!monthlySavings || monthlySavings <= 0) return null;
    return Math.ceil(closingCosts / monthlySavings);
  }
  function fmtUSD(n) {
    return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
  }
  function parseField(id) {
    var el = document.getElementById(id);
    if (!el) return 0;
    return parseFloat(el.value.replace(/[^0-9.]/g, '')) || 0;
  }
  return { monthlyPayment: monthlyPayment, dscr: dscr, maxLoan: maxLoan, originationFee: originationFee, balloonBalance: balloonBalance, breakeven: breakeven, fmtUSD: fmtUSD, parseField: parseField };
})();
