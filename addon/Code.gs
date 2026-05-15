// Update this URL each time ngrok is restarted (free tier assigns a new URL on each run).
var BACKEND_URL = "https://tableware-pastrami-quadrant.ngrok-free.dev/analyze";

var MAX_BODY_CHARS = 3000;

/**
 * Contextual trigger — called by Gmail whenever the user opens a message.
 * Extracts email fields, calls the backend, and returns a result card.
 */
function onGmailMessage(e) {
  try {
    var accessToken = e.gmail.accessToken;
    var messageId = e.gmail.messageId;

    GmailApp.setCurrentMessageAccessToken(accessToken);
    var message = GmailApp.getMessageById(messageId);

    var subject = message.getSubject() || "(no subject)";
    var sender = message.getFrom() || "(unknown sender)";
    var replyTo = message.getReplyTo() || "";
    var date = message.getDate() ? message.getDate().toISOString() : "";
    var body = (message.getPlainBody() || "").substring(0, MAX_BODY_CHARS);

    var emailData = {
      subject: subject,
      sender: sender,
      reply_to: replyTo,
      body: body,
      date: date
    };

    var result = callBackend(emailData);
    return buildResultCard(result);
  } catch (err) {
    return buildErrorCard("Failed to analyze email: " + err.message);
  }
}

/**
 * POSTs email data to the FastAPI backend and returns the parsed JSON result.
 * Returns { error: "..." } on any failure so callers never see an exception.
 */
function callBackend(emailData) {
  try {
    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(emailData),
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(BACKEND_URL, options);
    var code = response.getResponseCode();

    if (code !== 200) {
      return { error: "Backend returned status " + code + ". Check that the server is running." };
    }

    return JSON.parse(response.getContentText());
  } catch (err) {
    return { error: "Network error: " + err.message };
  }
}

/**
 * Builds a Gmail add-on card displaying the analysis result.
 * Delegates to buildErrorCard if the result contains an error field.
 */
function buildResultCard(result) {
  if (result.error) {
    return buildErrorCard(result.error);
  }

  var score = result.score;
  var verdict = result.verdict;
  var reasoning = result.reasoning;
  var flags = result.flags || [];

  var emoji;
  if (score <= 39) {
    emoji = "🟢";
  } else if (score <= 69) {
    emoji = "🟡";
  } else {
    emoji = "🔴";
  }

  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("Email Security Analysis")
        .setSubtitle("Malicious Email Scorer")
    );

  // Score and verdict section
  var summarySection = CardService.newCardSection()
    .addWidget(
      CardService.newTextParagraph()
        .setText("<b>" + emoji + " " + verdict + " — Score: " + score + "/100</b>")
    )
    .addWidget(
      CardService.newTextParagraph()
        .setText(reasoning)
    );

  card.addSection(summarySection);

  // Flags section — only shown when there are red flags to display
  if (flags.length > 0) {
    var flagsSection = CardService.newCardSection()
      .setHeader("Red Flags Detected");

    for (var i = 0; i < flags.length; i++) {
      flagsSection.addWidget(
        CardService.newTextParagraph()
          .setText("• " + flags[i])
      );
    }

    card.addSection(flagsSection);
  }

  // Footer disclaimer
  var footerSection = CardService.newCardSection()
    .addWidget(
      CardService.newTextParagraph()
        .setText("<i>Analysis powered by Gemini AI. Always use your own judgment.</i>")
    );

  card.addSection(footerSection);

  return card.build();
}

/**
 * Returns a minimal error card shown when analysis fails or the backend is unreachable.
 */
function buildErrorCard(message) {
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("Analysis Error")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextParagraph()
            .setText(message)
        )
    )
    .build();
}
