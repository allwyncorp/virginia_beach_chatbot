import React, { useState, useEffect, useRef } from 'react';
import { MessageBox } from 'react-chat-elements';
import 'react-chat-elements/dist/main.css';
import { FiRefreshCw } from 'react-icons/fi';
import { FaThumbsUp, FaThumbsDown, FaTimes } from 'react-icons/fa';
import './App.css';

function App() {
  const initialMessages = [
    {
      id: Date.now(),
      position: 'left',
      type: 'text',
      text: 'Hello, how can I help you today?',
      date: new Date(),
      isBot: true,
      isGreeting: true,
      feedback: null,
    },
  ];

  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [commentBoxId, setCommentBoxId] = useState(null);
  const [commentText, setCommentText] = useState('');
  const socketRef = useRef(null);
  const sessionId = "user-session-123";

  useEffect(() => {
    const socket = new WebSocket("wss://z3r09cyc97.execute-api.us-east-1.amazonaws.com/prod");
    socketRef.current = socket;
    return () => socket.close();
  }, []);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMessage = {
      id: Date.now(),
      position: 'right',
      type: 'text',
      text: input,
      date: new Date(),
      isBot: false,
    };
    setMessages(prev => [...prev, userMessage]);
    try {
      const res = await fetch("https://1tcs5phs5k.execute-api.us-east-1.amazonaws.com/prod/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input, sessionId }),
      });
      const data = await res.json();
      const botReply = data?.messages?.[0]?.content.replace(/<\/?(response|answer)>/g, '').trim() || 'No response from bot.';
      const botMessage = {
        id: Date.now() + 1,
        position: 'left',
        type: 'text',
        text: botReply,
        date: new Date(),
        isBot: true,
        isGreeting: false,
        feedback: null,
      };
      setMessages(prev => [...prev, botMessage]);
    } catch {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        position: 'left',
        type: 'text',
        text: 'Error communicating with bot.',
        date: new Date(),
        isBot: true,
        isGreeting: false,
        feedback: null,
      }]);
    }
    setInput('');
  };

  const startNewChat = () => {
    setMessages(initialMessages);
    setInput('');
    setCommentBoxId(null);
    setCommentText('');
  };

  const sendFeedback = (feedback, msg) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        action: 'submitFeedback',
        data: {
          sessionId,
          responseId: msg.id,
          messageText: msg.text,
          feedback,
        }
      }));
      setMessages(messages.map(m => m.id === msg.id ? { ...m, feedback } : m));
      setCommentBoxId(msg.id);
    }
  };

  const submitComment = () => {
    if (commentText && socketRef.current?.readyState === WebSocket.OPEN) {
      const msg = messages.find(m => m.id === commentBoxId);
      socketRef.current.send(JSON.stringify({
        action: 'submitFeedback',
        data: {
          sessionId,
          responseId: msg.id,
          messageText: msg.text,
          feedback: msg.feedback,
          comment: commentText,
        }
      }));
    }
    setCommentBoxId(null);
    setCommentText('');
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <button onClick={startNewChat} className="refresh-button" aria-label="Start New Chat">
          <FiRefreshCw size={14} />
          <span>New Chat</span>
        </button>
        <span className="chat-title">Virginia Beach Assistant</span>
      </div>

      <div className="chat-messages">
        {messages.map(msg => (
          <div key={msg.id} className="message-row">
            <div className="message-wrapper">
              <MessageBox
                position={msg.position}
                type={msg.type}
                text={msg.text}
                date={msg.date}
              />
              {msg.isBot && !msg.isGreeting && (
                <div className="bubble-feedback">
                  {!msg.feedback ? (
                    <div className="feedback-buttons">
                      <button onClick={() => sendFeedback('positive', msg)}>
                        <FaThumbsUp color="green" />
                      </button>
                      <button onClick={() => sendFeedback('negative', msg)}>
                        <FaThumbsDown color="red" />
                      </button>
                    </div>
                  ) : (
                    <div className="feedback-confirmation">✓ Thank you!</div>
                  )}
                </div>
              )}
            </div>

            {commentBoxId === msg.id && (
              <div className="comment-box small">
                <div className="comment-header">
                  <span>Comment (optional):</span>
                  <button onClick={() => setCommentBoxId(null)}><FaTimes /></button>
                </div>
                <textarea
                  value={commentText}
                  onChange={e => setCommentText(e.target.value)}
                  placeholder="Your comment..."
                />
                <button className="submit-comment" onClick={submitComment}>Submit</button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="chat-input">
        <input
          type="text"
          value={input}
          placeholder="Ask a question..."
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}

export default App;
