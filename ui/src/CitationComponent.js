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

// Generate citation text based on source title
const generateCitationText = (sourceTitle) => {
  // Use source title if available, otherwise use a simple fallback
  return sourceTitle || 'Learn more';
};

const CitationComponent = ({ content, citations = [] }) => {
  // Filter out invalid URLs
  const validCitations = citations.filter(citation => isValidUrl(citation.url));
  
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
              aria-label={`${generateCitationText(citation.sourceTitle)} - opens in new tab`}
            >
              {generateCitationText(citation.sourceTitle)}
            </a>
          ))}
        </div>
      )}
    </div>
  );
};

export default CitationComponent; 