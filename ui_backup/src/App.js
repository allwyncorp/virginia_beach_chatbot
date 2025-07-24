import React, { useState, useEffect } from 'react';
import './App.css';

// const API_URL = process.env.REACT_APP_API_URL || '/chat'; // Set this to your API Gateway endpoint
const API_URL = "https://t72e3ey24i.execute-api.us-east-1.amazonaws.com/prod/chat";

function App() {
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Hello, how can I help you today?' }
  ]);
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMessage = { from: 'user', text: inputValue };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');

    try {
      const response = await fetch(`${API_URL}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: inputValue,
          sessionId: 'test-session'
        })
      });
      const data = await response.json();
      if (data.messages && data.messages.length > 0) {
        const botMessage = { from: 'bot', text: data.messages[0].content };
        setMessages(prev => [...prev, botMessage]);
      } else {
        setMessages(prev => [...prev, { from: 'bot', text: 'Sorry, I didn\'t understand that.' }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, { from: 'bot', text: 'Error communicating with backend.' }]);
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
            <p>{message.text}</p>
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
        />
        <button type="submit" className="send-button">Send</button>
      </form>
    </div>
  );
}

export default App;
