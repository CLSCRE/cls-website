// Google Apps Script — paste this into Extensions > Apps Script in your Google Sheet
// Then Deploy > New Deployment > Web App > Anyone can access > Deploy
// Copy the URL and give it to Claude to plug into the form

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Submissions");
  var data = JSON.parse(e.postData.contents);

  sheet.appendRow([
    new Date().toLocaleString("en-US", {timeZone: "America/Los_Angeles"}),
    data["First Name"] || "",
    data["Last Name"] || "",
    data["Company"] || "",
    data["Email"] || "",
    data["Phone"] || "",
    data["License Number"] || "",
    data["Property Type"] || "",
    data["City and State"] || "",
    data["Property Address"] || "",
    data["Units or SF"] || "",
    data["Year Built"] || "",
    data["Occupancy"] || "",
    data["Loan Amount"] || "",
    data["Loan Type"] || "",
    data["Loan Purpose"] || "",
    data["Timeline"] || "",
    data["Property Value"] || "",
    data["NOI"] || "",
    data["Deal Summary"] || "",
    data["Referral Source"] || ""
  ]);

  // Also send email notification
  var subject = "New Deal Submission — " + data["First Name"] + " " + data["Last Name"] + " (" + data["Company"] + ")";
  var body = "New deal submitted via Broker Portal:\n\n";
  for (var key in data) {
    if (key.charAt(0) !== "_" && key !== "website_url" && key !== "Form Loaded At" && key !== "Confirmed") {
      body += key + ": " + data[key] + "\n";
    }
  }
  MailApp.sendEmail("inquiries@clscre.com", subject, body);

  return ContentService
    .createTextOutput(JSON.stringify({status: "success"}))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({status: "ok", message: "CLS CRE Deal Submission endpoint"}))
    .setMimeType(ContentService.MimeType.JSON);
}
