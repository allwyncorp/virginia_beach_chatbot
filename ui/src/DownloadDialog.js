import React, { useState, useEffect } from 'react';
import './DownloadDialog.css';

const DownloadDialog = ({ isOpen, onClose, onDownload, messages }) => {
  const [selectedFormat, setSelectedFormat] = useState('txt');

  const formatOptions = [
    {
      value: 'txt',
      label: 'Plain Text (.txt)',
      description: 'Simple text format, compatible with any text editor'
    },
    {
      value: 'pdf',
      label: 'PDF Document (.pdf)',
      description: 'Professional document format, preserves formatting'
    },
    {
      value: 'docx',
      label: 'Word Document (.docx)',
      description: 'Microsoft Word format, editable and well-formatted'
    },
    {
      value: 'md',
      label: 'Markdown (.md)',
      description: 'Lightweight markup format, great for documentation'
    },
    {
      value: 'csv',
      label: 'CSV (.csv)',
      description: 'Spreadsheet format, useful for data analysis'
    }
  ];

  useEffect(() => {
    // Load saved preference
    const savedFormat = localStorage.getItem('preferredDownloadFormat');
    if (savedFormat) {
      setSelectedFormat(savedFormat);
    }
  }, []);

  useEffect(() => {
    // Handle escape key
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  const handleDownload = () => {
    onDownload(selectedFormat);
    onClose();
  };

  const handleFormatChange = (format) => {
    setSelectedFormat(format);
  };

  if (!isOpen) return null;

  return (
    <div className="download-dialog-overlay" onClick={onClose}>
      <div className="download-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="download-dialog-header">
          <h3>Download Conversation</h3>
          <button 
            className="download-dialog-close" 
            onClick={onClose}
            aria-label="Close dialog"
          >
            ×
          </button>
        </div>
        <div className="download-dialog-content">
          {messages.length <= 1 ? (
            <div className="no-conversation-message">
              <p>No conversation to download yet. Start chatting with the Virginia Beach Assistant to download your conversation.</p>
            </div>
          ) : (
            <>
              <p className="download-dialog-description">
                Choose a format to download your conversation:
              </p>
              <div className="format-options">
                {formatOptions.map((option) => (
                  <div 
                    key={option.value}
                    className={`format-option ${selectedFormat === option.value ? 'selected' : ''}`}
                    onClick={() => handleFormatChange(option.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleFormatChange(option.value);
                      }
                    }}
                    tabIndex={0}
                    role="radio"
                    aria-checked={selectedFormat === option.value}
                  >
                    <div className="format-option-radio">
                      <div className={`radio-button ${selectedFormat === option.value ? 'checked' : ''}`}></div>
                    </div>
                    <div className="format-option-content">
                      <div className="format-option-label">{option.label}</div>
                      <div className="format-option-description">{option.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
        <div className="download-dialog-actions">
          <button 
            className="download-dialog-button cancel-button" 
            onClick={onClose}
          >
            Cancel
          </button>
          <button 
            className="download-dialog-button download-button" 
            onClick={handleDownload}
            disabled={messages.length <= 1}
          >
            {messages.length <= 1 ? 'No Conversation' : 'Download'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DownloadDialog; 