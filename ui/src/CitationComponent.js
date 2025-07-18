import React from 'react';

// URL validation function
const isValidUrl = (url) => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

// Generate citation text based on title
const generateCitationText = (title) => {
  // Use title if available, otherwise use a simple fallback
  return title || 'Learn more';
};

const CitationComponent = ({ content, citations = [] }) => {
  // Debug logging
  console.log('CitationComponent received:', { content, citations });
  
  // Filter out invalid URLs
  const validCitations = citations.filter(citation => {
    const isValid = isValidUrl(citation.url);
    console.log('Citation validation:', { citation, isValid });
    return isValid;
  });
  
  console.log('Valid citations:', validCitations);
  
  // Add a test citation for debugging
  const testCitations = [
    {
      title: "Test Citation",
      url: "https://virginiabeach.gov"
    }
  ];
  
  return (
    <div className="citation-content">
      <p>{content}</p>
      {validCitations.length > 0 && (
        <div className="citations">
          {validCitations.map((citation, index) => (
            <a
              key={index}
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="citation-link"
              aria-label={`${generateCitationText(citation.title)} - opens in new tab`}
            >
              {generateCitationText(citation.title)}
            </a>
          ))}
        </div>
      )}
      {/* Test citation to verify styling */}
      {validCitations.length === 0 && (
        <div className="citations">
          <p style={{fontSize: '0.75rem', color: '#666', fontStyle: 'italic'}}>
            Debug: No valid citations found. Test citation below:
          </p>
          {testCitations.map((citation, index) => (
            <a
              key={`test-${index}`}
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="citation-link"
              aria-label={`${generateCitationText(citation.title)} - opens in new tab`}
            >
              {generateCitationText(citation.title)}
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default CitationComponent; 