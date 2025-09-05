// content.js
// Extracts LinkedIn job descriptions when asked

/*
DOM SCANNING STRATEGY:
- The "About this job" header text is usually inside an <h2> or <span> element — it's stable across multiple LinkedIn layouts.
- We:
  1. Search for any heading that matches "About this job" (supporting localization if needed)
  2. Find the first reasonably large block of text after that header.
  3. Only return plain text (avoid copying formatting/js/ads)

*/

// Listen for messages from the extension (popup.js)
chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
  if (msg && msg.type === "SCAN_LINKEDIN_JD") {
    try {
      // 1. Find "About this job" heading
      let aboutHeader = Array.from(document.querySelectorAll("h2, h3, span, div"))
        .filter(
          (el) =>
            el.innerText &&
            el.innerText.trim().toLowerCase().replace(/[^a-z]/g, "").includes("aboutthejob")
        )[0];

      // Robust fallback if not found: try a substring match for 'about'
      if (!aboutHeader) {
        aboutHeader = Array.from(document.querySelectorAll("h2, h3, span, div"))
          .filter(
            (el) =>
              el.innerText &&
              el.innerText.trim().toLowerCase().includes("about")
          )[0];
      }

      if (!aboutHeader) {
        sendResponse([{ success: false, error: "Could not find 'About this job' section on this page." }]);
        return;
      }

      // 2. Get next content node after the header (may be a parent, may need to climb DOM)
      let descNode = aboutHeader.nextElementSibling;
      let tried = 0;

      // Sometimes, the first sibling is not the JD; skip until we find a substantial amount of text.
      while (
        descNode &&
        (descNode.innerText.trim().length < 50 || descNode.offsetHeight < 40) &&
        tried < 5
      ) {
        descNode = descNode.nextElementSibling;
        tried++;
      }

      // If sibling fails, try going up to parent and searching downward for main text block
      if (!descNode || descNode.innerText.trim().length < 50) {
        // Find the closest block element with lots of text
        let candidates = Array.from(
          aboutHeader.closest("section, div, article")?.querySelectorAll("span, div, p") || []
        ).filter((el) => el.innerText && el.innerText.length > 60);
        descNode = candidates[0];
      }

      // Final check
      if (!descNode || !descNode.innerText || descNode.innerText.length < 50) {
        sendResponse([{ success: false, error: "Could not find job description body. LinkedIn page structure may have changed." }]);
        return;
      }

      // 3. Return the extracted text for the extension to use
      sendResponse([{ success: true, data: descNode.innerText.trim() }]);
    } catch (err) {
      sendResponse([{ success: false, error: err.message }]);
    }
    // Mark as asynchronous response
    return true;
  }
});
