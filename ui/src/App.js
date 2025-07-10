import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import DownloadDialog from './DownloadDialog';
import { downloadConversation } from './downloadUtils';

// WebSocket endpoint - updated with actual deployment endpoint
const WEBSOCKET_URL = process.env.REACT_APP_WEBSOCKET_URL || 'wss://ejlemeved3.execute-api.us-east-1.amazonaws.com/prod';

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Hello, how can I help you today?' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [showDownloadDialog, setShowDownloadDialog] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  
  const wsRef = useRef(null);
  const currentBotMessageRef = useRef(null);

  useEffect(() => {
    // Initialize WebSocket connection
    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    try {
      console.log('Connecting to WebSocket:', WEBSOCKET_URL);
      wsRef.current = new WebSocket(WEBSOCKET_URL);
      
      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
      };
      
      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
          if (!isConnected) {
            connectWebSocket();
          }
        }, 3000);
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
      
      wsRef.current.onmessage = (event) => {
        handleWebSocketMessage(event.data);
      };
      
    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
    }
  };

  const stopStreaming = () => {
    console.log('Stopping streaming...');
    
    // Close the WebSocket connection to stop streaming
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    
    // Reset streaming state
    setIsStreaming(false);
    
    // Update the current bot message to remove streaming state
    setMessages(prev => {
      const newMessages = [...prev];
      const botMessageIndex = newMessages.length - 1;
      
      if (newMessages[botMessageIndex] && newMessages[botMessageIndex].from === 'bot') {
        newMessages[botMessageIndex] = {
          ...newMessages[botMessageIndex],
          isStreaming: false
        };
      }
      
      return newMessages;
    });
    
    // Reconnect WebSocket after a short delay
    setTimeout(() => {
      connectWebSocket();
    }, 100);
  };

  const handleWebSocketMessage = (data) => {
    try {
      const message = JSON.parse(data);
      console.log('Received WebSocket message:', message);
      
      switch (message.type) {
        case 'message_received':
          // Server acknowledged the message
          console.log('Message acknowledged by server');
          break;
          
        case 'stream_start':
          // Streaming is starting
          console.log('Streaming started');
          setIsStreaming(true);
          break;
          
        case 'stream_chunk':
          // Handle streaming chunk
          handleStreamChunk(message.content);
          break;
          
        case 'stream_complete':
          // Streaming completed
          console.log('Streaming completed:', message.full_response);
          handleStreamComplete(message.full_response);
          break;
          
        case 'stream_error':
          // Handle streaming error
          console.error('Streaming error:', message.error);
          handleStreamError(message.error);
          break;
          
        case 'error':
          // Handle general error
          console.error('WebSocket error:', message.error);
          handleStreamError(message.error);
          break;
          
        default:
          console.log('Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  const handleStreamChunk = (chunk) => {
    setMessages(prev => {
      const newMessages = [...prev];
      const botMessageIndex = newMessages.length - 1;
      
      if (newMessages[botMessageIndex] && newMessages[botMessageIndex].from === 'bot') {
        // Append the chunk to the current bot message
        newMessages[botMessageIndex] = {
          ...newMessages[botMessageIndex],
          text: (newMessages[botMessageIndex].text || '') + chunk,
          isStreaming: true
        };
        currentBotMessageRef.current = newMessages[botMessageIndex];
      }
      
      return newMessages;
    });
  };

  const handleStreamComplete = (fullResponse) => {
    setMessages(prev => {
      const newMessages = [...prev];
      const botMessageIndex = newMessages.length - 1;
      
      if (newMessages[botMessageIndex] && newMessages[botMessageIndex].from === 'bot') {
        newMessages[botMessageIndex] = {
          ...newMessages[botMessageIndex],
          text: fullResponse,
          isStreaming: false
        };
      }
      
      return newMessages;
    });
    
    setIsStreaming(false);
  };

  const handleStreamError = (errorMessage) => {
    setMessages(prev => {
      const newMessages = [...prev];
      const botMessageIndex = newMessages.length - 1;
      
      if (newMessages[botMessageIndex] && newMessages[botMessageIndex].from === 'bot') {
        newMessages[botMessageIndex] = {
          ...newMessages[botMessageIndex],
          text: errorMessage,
          isStreaming: false
        };
      }
      
      return newMessages;
    });
    
    setIsStreaming(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isStreaming || !isConnected) return;

    console.log('Sending message via WebSocket:', inputValue);

    const userMessage = { from: 'user', text: inputValue };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);

    // Add empty bot message that will be filled with streaming content
    setMessages(prev => [...prev, { from: 'bot', text: '', isStreaming: true }]);

    try {
      // Send message via WebSocket
      const message = {
        message: inputValue,
        sessionId: `session-${Date.now()}`
      };
      
      wsRef.current.send(JSON.stringify(message));
      console.log('Message sent via WebSocket');
      
    } catch (error) {
      console.error('Error sending message:', error);
      handleStreamError('Error sending message. Please try again.');
    }
  };

  const handleDownloadClick = () => {
    setShowDownloadDialog(true);
  };

  const handleDownloadClose = () => {
    setShowDownloadDialog(false);
  };

  const handleDownload = async (format) => {
    setIsDownloading(true);
    try {
      await downloadConversation(messages, format);
    } catch (error) {
      console.error('Download failed:', error);
      // Show a more user-friendly error message
      const errorMessage = error.message === 'No conversation to download' 
        ? 'No conversation to download. Please start a conversation first.'
        : 'Download failed. Please try again.';
      alert(errorMessage);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Virginia Beach Assistant</h2>
        <button 
          className="download-button"
          onClick={handleDownloadClick}
          disabled={messages.length <= 1 || isDownloading}
          title={messages.length <= 1 ? "No conversation to download" : "Download conversation"}
        >
          {isDownloading ? '⏳ Downloading...' : '📥 Download'}
        </button>
      </div>
      <div className="message-list">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.from}`}>
            <p>
              {message.text}
            </p>
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="message-form">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={isConnected ? "Ask a question..." : "Connecting..."}
          className="message-input"
          disabled={isStreaming || !isConnected}
        />
        <button 
          type={isStreaming ? "button" : "submit"} 
          className={`send-button ${isStreaming ? 'stop-button' : ''}`} 
          disabled={!isConnected}
          onClick={isStreaming ? stopStreaming : undefined}
        >
          {isStreaming ? 'Stop' : 'Send'}
        </button>
      </form>
      
      <DownloadDialog
        isOpen={showDownloadDialog}
        onClose={handleDownloadClose}
        onDownload={handleDownload}
        messages={messages}
      />
    </div>
  );
}

export default App;
