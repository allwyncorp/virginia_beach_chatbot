import React, { useState } from 'react';
import './App.css';

// const API_URL = process.env.REACT_APP_API_URL || '/chat'; // Set this to your API Gateway endpoint
const API_URL = "https://t72e3ey24i.execute-api.us-east-1.amazonaws.com/prod";

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Hello, how can I help you today?' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isStreaming) return;

    console.log('Starting chat request:', inputValue);

    const userMessage = { from: 'user', text: inputValue };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);

    setMessages(prev => [...prev, { from: 'bot', text: '', isStreaming: true }]);

    try {
      console.log('Making request to streaming endpoint...');
      
      const response = await fetch(`${API_URL}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: inputValue,
          sessionId: 'test-session'
        })
      });

      console.log('Response received:', response.status, response.statusText);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let completeMessage = '';
      let chunkCount = 0;

      console.log('Starting to read streaming response...');

      // Read the SSE response to get the complete message
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          console.log('Finished reading response stream');
          break;
        }
        
        chunkCount++;
        const chunk = decoder.decode(value);
        console.log(`Chunk ${chunkCount}:`, chunk.substring(0, 100) + (chunk.length > 100 ? '...' : ''));
        
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              console.log('Parsed SSE data:', data);
              
              if (data.type === 'message' && data.content) {
                completeMessage = data.content;
                console.log('Complete message received:', completeMessage);
                break;
              } else if (data.type === 'error') {
                throw new Error(data.content || 'Unknown error');
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError, 'Line:', line);
            }
          }
        }
      }

      if (!completeMessage) {
        throw new Error('No message received from server');
      }

      console.log('Complete message:', completeMessage);

      const words = completeMessage.split(' ');
      let currentText = '';
      console.log('Starting typing simulation...');
      console.log('Words to type:', words);
      
      for (let i = 0; i < words.length; i++) {
        const word = words[i];
        currentText += (i === 0 ? '' : ' ') + word;
        
        console.log(`Typing word ${i + 1}/${words.length}: "${word}" -> Current text: "${currentText}"`);
        
        // Update the message with the current text
        setMessages(prev => {
          const newMessages = [...prev];
          const botMessageIndex = newMessages.length - 1;
          if (newMessages[botMessageIndex] && newMessages[botMessageIndex].from === 'bot') {
            newMessages[botMessageIndex] = {
              ...newMessages[botMessageIndex],
              text: currentText,
              isStreaming: i < words.length - 1
            };
          }
          return newMessages;
        });

        if (i < words.length - 1) {
          const delay = 50 + Math.random() * 100;
          console.log(`⏱️  Waiting ${Math.round(delay)}ms before next word...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }

  
      setIsStreaming(false);
    } catch (error) {
      console.error('Streaming error:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        const botMessageIndex = newMessages.length - 1;
        if (newMessages[botMessageIndex] && newMessages[botMessageIndex].from === 'bot') {
          newMessages[botMessageIndex] = {
            ...newMessages[botMessageIndex],
            text: 'Error communicating with backend.',
            isStreaming: false
          };
        }
        return newMessages;
      });
      setIsStreaming(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Virginia Beach Assistant</h2>
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
          placeholder="Ask a question..."
          className="message-input"
          disabled={isStreaming}
        />
        <button type="submit" className="send-button" disabled={isStreaming}>
          {isStreaming ? 'Sending...' : 'Send'}
        </button>
      </form>
    </div>
  );
}

export default App;
