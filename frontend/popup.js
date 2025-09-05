// popup.js
// Main React logic for the popup, with detailed beginner-friendly comments

// Import React and ReactDOM from the global window (CDN)
const { useState } = React;
const e = React.createElement;

// A fancy Spinner component for loading state, for clear user feedback
function Spinner() {
  return e(
    "div",
    { className: "flex justify-center py-3" },
    e(
      "svg",
      {
        className: "animate-spin h-7 w-7 text-blue-500",
        viewBox: "0 0 24 24",
        fill: "none"
      },
      e("circle", {
        className: "opacity-25",
        cx: "12",
        cy: "12",
        r: "10",
        stroke: "currentColor",
        strokeWidth: "4"
      }),
      e("path", {
        className: "opacity-75",
        fill: "currentColor",
        d: "M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      })
    )
  );
}

// Main App component
function App() {
  // State: loading indicators, results, error, PDF file info
  const [scanLoading, setScanLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState(""); // show errors for robust UX
  const [jobDesc, setJobDesc] = useState(""); // raw extracted JD
  const [resumeFilename, setResumeFilename] = useState("");
  // New: textarea for pasting JD
  const [pastedJD, setPastedJD] = useState("");
    // Track if we're on LinkedIn
  const [onLinkedIn, setOnLinkedIn] = useState(false);
  // Placeholders for AI-driven results
  const [suggestedSkills, setSuggestedSkills] = useState([]);
  const [atsScore, setAtsScore] = useState(null);
  const [improvementAdvice, setImprovementAdvice] = useState([]);

  // On mount, check if current tab is LinkedIn
  React.useEffect(() => {
    // Check if Chrome extension APIs are available
    if (!chrome || !chrome.tabs) {
      console.warn("Chrome extension APIs not available");
      setOnLinkedIn(false);
      return;
    }

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      // Check for Chrome API errors
      if (chrome.runtime.lastError) {
        console.error("Chrome tabs API error:", chrome.runtime.lastError.message);
        setOnLinkedIn(false);
        return;
      }

      // Check if we got valid tab data
      if (tabs && tabs[0] && tabs[0].url && tabs[0].url.includes("linkedin.com/jobs")) {
        setOnLinkedIn(true);
      } else {
        setOnLinkedIn(false);
      }
    });
  }, []);


  // Handler: scan the pasted JD and uploaded resume by sending to backend
  const handleScanAnyJob = async () => {
    try {
      setScanLoading(true);
      setError("");
      setJobDesc("");
      setSuggestedSkills([]);
      setAtsScore(null);
      setImprovementAdvice([]);

      // Validate inputs
      if (!pastedJD.trim()) {
        throw new Error("Please paste a job description to scan.");
      }
      if (!resumeFile) {
        throw new Error("Please upload a resume (PDF or DOCX) before scanning.");
      }

      // Prepare form data for backend
      const formData = new FormData();
      formData.append("jd_text", pastedJD);
      formData.append("resume", resumeFile);

      // POST to backend API with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      try {
        const response = await fetch("http://localhost:8000/process", {
          method: "POST",
          body: formData,
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail?.message || errData.error || `HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("Backend response:", data);
        
        // Update state with backend response
        setJobDesc(data.jd_text || "");
        setAtsScore(typeof data.ats_score === "number" ? data.ats_score : null);
        setSuggestedSkills(Array.isArray(data.suggested_skills) ? data.suggested_skills : []);
        setImprovementAdvice(Array.isArray(data.improvement_recommendation) ? data.improvement_recommendation : []);
        
      } catch (err) {
        if (err.name === 'AbortError') {
          throw new Error("Request timed out. Please try again.");
        }
        throw err;
      }
    } catch (err) {
      console.error("Scan error:", err);
      setError(err.message.startsWith("Error: ") ? err.message : `Error: ${err.message}`);
      setJobDesc("");
      setSuggestedSkills([]);
      setImprovementAdvice([]);
      setAtsScore(null);
    } finally {
      setScanLoading(false);
    }
  };

  // Store uploaded resume file for later scan
  const [resumeFile, setResumeFile] = useState(null);

  // Handler: PDF/DOCX resume upload
  const handleUploadResume = (event) => {
    setPdfLoading(true);
    setError("");
    setResumeFilename("");
    const file = event.target.files[0];
    if (!file) {
      setPdfLoading(false);
      return;
    }
    if (!["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"].includes(file.type)
      && !file.name.endsWith(".pdf") && !file.name.endsWith(".docx")) {
      setError("Resume must be a PDF or DOCX file.");
      setPdfLoading(false);
      event.target.value = null;
      return;
    }
    setResumeFilename(file.name + " (" + Math.round(file.size / 1024) + " KB)");
    setResumeFile(file);
    setPdfLoading(false);
  };



  // UI: return full structure with visual order and clear headings
  return e(
    "div",
    {
      className:
        "p-5 flex flex-col gap-4 h-full rounded-xl shadow bg-white"
    },
    // Main Title
    e(
      "h1",
      { className: "text-2xl font-bold text-gray-800 text-center mb-2" },
      "NLP Resume Optimizer"
    ),
    // Description
    e(
      "p",
      { className: "text-gray-600 text-center text-base mb-2" },
      "Optimize your resume for ATS. Scan any job or LinkedIn jobs and upload your resume for tips!"
    ),
    // Paste JD textarea
    e(
      "textarea",
      {
        className:
          "w-full border border-gray-300 rounded-lg p-2 mb-2 text-sm min-h-[60px] resize-none focus:outline-blue-400",
        placeholder: "Paste any job description here (works on any website)...",
        value: pastedJD,
        onChange: (e) => setPastedJD(e.target.value),
        disabled: scanLoading
      }
    ),
    // SCAN ANY JOB BUTTON
    e(
      "button",
      {
        className:
          "w-full bg-blue-500 hover:bg-blue-700 text-white py-2 px-4 rounded-lg font-semibold shadow transition mb-1",
        onClick: handleScanAnyJob,
        disabled: scanLoading
      },
      scanLoading ? e(Spinner, {}) : null,
      scanLoading ? "Scanning..." : "Scan This Job (Paste Job Description Above)"
    ),

    // PDF upload section
    e(
      "label",
      {
        className:
          "block cursor-pointer mt-1 w-full bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded-lg font-semibold shadow transition text-center"
      },
      pdfLoading ? e(Spinner, {}) : "Upload Resume (PDF)",
      e("input", {
        type: "file",
        accept: ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        className: "hidden",
        onChange: handleUploadResume,
        disabled: pdfLoading
      })
    ),
    // Display error if any
    error &&
      e(
        "div",
        { className: "bg-red-100 text-red-700 px-3 py-2 rounded mb-2 text-sm border border-red-200" },
        error
      ),
    // Show job description extract
    jobDesc &&
      e(
        "section",
        { className: "mb-2" },
        e("h2", { className: "text-lg font-semibold mt-2 text-gray-700" }, "Job Description Extract"),
        e("p", { className: "text-gray-600 whitespace-pre-wrap text-sm max-h-32 overflow-y-auto rounded bg-gray-50 px-2 py-1 mt-1" }, jobDesc)
      ),
    // PDF Metadata placeholder
    resumeFilename &&
      e(
        "div",
        { className: "bg-gray-100 text-gray-800 px-2 py-1 rounded text-sm mb-1 mt-1" },
        "Resume Uploaded: " + resumeFilename
      ),
    // Results Area: visually separated
    e(
      "section",
      { className: "mt-4 space-y-2" },
      // 1. ATS Score placeholder
      e(
        "div",
        {
          className:
            "flex items-center gap-2 bg-blue-100 rounded px-2 py-1"
        },
        e("span", { className: "font-semibold text-blue-800" }, "ATS Score:"),
        atsScore !== null
          ? e(
              "span",
              {
                className: "font-bold text-blue-700"
              },
              atsScore + "%"
            )
          : e("span", { className: "text-blue-400 italic" }, "Not calculated")
      ),
      // 2. Suggested Skills (always visible)
      e(
        "div",
        { className: "mt-2 p-3 bg-yellow-50 rounded-lg border border-yellow-100" },
        e("span", { className: "font-semibold text-yellow-800" }, "Suggested Skills to Add:"),
        suggestedSkills && suggestedSkills.length > 0
          ? e(
              "div",
              { className: "max-h-32 overflow-y-auto mt-2" },
              e(
                "ul",
                { className: "list-disc list-inside text-yellow-700 space-y-1" },
                suggestedSkills.map((skill, i) =>
                  e("li", { key: i, className: "text-sm" }, skill)
                )
              )
            )
          : e("span", { className: "text-yellow-500 italic text-sm mt-2 block" }, "No suggestions yet")
      ),
      // 3. Improvement/Restructuring Advice
      improvementAdvice && improvementAdvice.length > 0 && e(
        "div",
        { className: "mt-4 p-4 bg-yellow-50 rounded-lg border border-yellow-200" },
        e("h3", { className: "font-bold text-yellow-800 text-lg mb-3" }, "Improvement Recommendations"),
        e(
          "div",
          { className: "max-h-48 overflow-y-auto space-y-3" },
          improvementAdvice.map((item, index) => (
            e(
              "div",
              {
                key: index,
                className: "bg-yellow-100 p-3 rounded-lg border-l-4 border-yellow-400"
              },
              e("p", { className: "font-medium text-yellow-800" }, item.issue || "Improvement needed"),
              e("p", { className: "text-yellow-700 text-sm mt-1" }, item.advice || "No specific advice available.")
            )
          ))
        )
      ),

      null
    )
  );
}

// Mount our React app inside popup.html
ReactDOM.render(e(App), document.getElementById("root"));
