import jsPDF from 'jspdf';
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx';
import { saveAs } from 'file-saver';

// Generate metadata for the conversation
const generateMetadata = (messages) => {
  const startTime = new Date();
  const endTime = new Date();
  
  if (messages.length > 1) {
  }
  
  return {
    title: 'Virginia Beach Assistant Conversation',
    startTime: startTime.toLocaleString(),
    endTime: endTime.toLocaleString(),
    messageCount: messages.length,
    participants: ['User', 'Virginia Beach Assistant']
  };
};

// Convert messages to plain text format
const formatAsText = (messages, metadata) => {
  let content = `${metadata.title}\n`;
  content += `Generated on: ${new Date().toLocaleString()}\n`;
  content += `Total messages: ${metadata.messageCount}\n`;
  content += '='.repeat(50) + '\n\n';
  
  messages.forEach((message, index) => {
    const sender = message.from === 'user' ? 'User' : 'Virginia Beach Assistant';
    
    // Extract clean text content (remove citation links)
    let cleanText = message.text;
    
    // If message has structured content with citations, extract only the content
    if (typeof message.text === 'string' && message.text.includes('"content"')) {
      try {
        const parsed = JSON.parse(message.text);
        if (parsed.content) {
          cleanText = parsed.content;
        }
      } catch (e) {
        // If parsing fails, use the original text
        cleanText = message.text;
      }
    }
    
    content += `${sender}:\n${cleanText}\n\n`;
  });
  
  return content;
};

// Convert messages to Markdown format
const formatAsMarkdown = (messages, metadata) => {
  let content = `# ${metadata.title}\n\n`;
  content += `**Generated on:** ${new Date().toLocaleString()}\n`;
  content += `**Total messages:** ${metadata.messageCount}\n\n`;
  content += '---\n\n';
  
  messages.forEach((message, index) => {
    const sender = message.from === 'user' ? '**User:**' : '**Virginia Beach Assistant:**';
    
    // Extract clean text content (remove citation links)
    let cleanText = message.text;
    
    // If message has structured content with citations, extract only the content
    if (typeof message.text === 'string' && message.text.includes('"content"')) {
      try {
        const parsed = JSON.parse(message.text);
        if (parsed.content) {
          cleanText = parsed.content;
        }
      } catch (e) {
        // If parsing fails, use the original text
        cleanText = message.text;
      }
    }
    
    content += `${sender}\n\n${cleanText}\n\n`;
  });
  
  return content;
};

// Convert messages to CSV format
const formatAsCSV = (messages, metadata) => {
  let content = 'Timestamp,Sender,Message\n';
  
  messages.forEach((message, index) => {
    const sender = message.from === 'user' ? 'User' : 'Virginia Beach Assistant';
    const timestamp = new Date().toISOString(); // Could be enhanced with actual timestamps
    
    // Extract clean text content (remove citation links)
    let cleanText = message.text;
    
    // If message has structured content with citations, extract only the content
    if (typeof message.text === 'string' && message.text.includes('"content"')) {
      try {
        const parsed = JSON.parse(message.text);
        if (parsed.content) {
          cleanText = parsed.content;
        }
      } catch (e) {
        // If parsing fails, use the original text
        cleanText = message.text;
      }
    }
    
    const escapedMessage = cleanText.replace(/"/g, '""'); // Escape quotes for CSV
    content += `"${timestamp}","${sender}","${escapedMessage}"\n`;
  });
  
  return content;
};

// Generate PDF document
const generatePDF = async (messages, metadata) => {
  const pdf = new jsPDF();
  
  // Add title
  pdf.setFontSize(18);
  pdf.setFont('helvetica', 'bold');
  pdf.text(metadata.title, 20, 20);
  
  // Add metadata
  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  pdf.text(`Generated on: ${new Date().toLocaleString()}`, 20, 35);
  pdf.text(`Total messages: ${metadata.messageCount}`, 20, 42);
  
  // Add separator line
  pdf.line(20, 50, 190, 50);
  
  let yPosition = 65;
  const lineHeight = 7;
  const maxWidth = 170;
  
  messages.forEach((message, index) => {
    const sender = message.from === 'user' ? 'User' : 'Virginia Beach Assistant';
    
    // Add sender name
    pdf.setFontSize(12);
    pdf.setFont('helvetica', 'bold');
    pdf.text(sender + ':', 20, yPosition);
    yPosition += lineHeight;
    
    // Add message text
    pdf.setFontSize(10);
    pdf.setFont('helvetica', 'normal');
    
    // Extract clean text content (remove citation links)
    let cleanText = message.text;
    
    // If message has structured content with citations, extract only the content
    if (typeof message.text === 'string' && message.text.includes('"content"')) {
      try {
        const parsed = JSON.parse(message.text);
        if (parsed.content) {
          cleanText = parsed.content;
        }
      } catch (e) {
        // If parsing fails, use the original text
        cleanText = message.text;
      }
    }
    
    // Split long messages into multiple lines
    const words = cleanText.split(' ');
    let line = '';
    
    for (let word of words) {
      const testLine = line + word + ' ';
      const testWidth = pdf.getTextWidth(testLine);
      
      if (testWidth > maxWidth && line !== '') {
        pdf.text(line, 20, yPosition);
        yPosition += lineHeight;
        line = word + ' ';
      } else {
        line = testLine;
      }
    }
    
    if (line) {
      pdf.text(line, 20, yPosition);
      yPosition += lineHeight * 2;
    }
    
    // Add page break if needed
    if (yPosition > 270) {
      pdf.addPage();
      yPosition = 20;
    }
  });
  
  return pdf;
};

// Generate DOCX document
const generateDOCX = async (messages, metadata) => {
  const children = [];
  
  // Add title
  children.push(
    new Paragraph({
      text: metadata.title,
      heading: HeadingLevel.HEADING_1,
      spacing: { after: 200 }
    })
  );
  
  // Add metadata
  children.push(
    new Paragraph({
      children: [
        new TextRun({
          text: `Generated on: ${new Date().toLocaleString()}`,
          bold: false
        })
      ],
      spacing: { after: 100 }
    })
  );
  
  children.push(
    new Paragraph({
      children: [
        new TextRun({
          text: `Total messages: ${metadata.messageCount}`,
          bold: false
        })
      ],
      spacing: { after: 200 }
    })
  );
  
  // Add messages
  messages.forEach((message, index) => {
    const sender = message.from === 'user' ? 'User' : 'Virginia Beach Assistant';
    
    children.push(
      new Paragraph({
        children: [
          new TextRun({
            text: sender + ':',
            bold: true
          })
        ],
        spacing: { after: 100 }
      })
    );
    
    // Extract clean text content (remove citation links)
    let cleanText = message.text;
    
    // If message has structured content with citations, extract only the content
    if (typeof message.text === 'string' && message.text.includes('"content"')) {
      try {
        const parsed = JSON.parse(message.text);
        if (parsed.content) {
          cleanText = parsed.content;
        }
      } catch (e) {
        // If parsing fails, use the original text
        cleanText = message.text;
      }
    }
    
    children.push(
      new Paragraph({
        children: [
          new TextRun({
            text: cleanText,
            bold: false
          })
        ],
        spacing: { after: 200 }
      })
    );
  });
  
  const doc = new Document({
    sections: [{
      properties: {},
      children: children
    }]
  });
  
  return await Packer.toBlob(doc);
};

// Main download function
export const downloadConversation = async (messages, format) => {
  if (messages.length <= 1) {
    throw new Error('No conversation to download');
  }
  
  const metadata = generateMetadata(messages);
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filename = `virginia-beach-conversation-${timestamp}`;
  
  try {
    switch (format) {
      case 'txt':
        const textContent = formatAsText(messages, metadata);
        const textBlob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
        saveAs(textBlob, `${filename}.txt`);
        break;
        
      case 'md':
        const markdownContent = formatAsMarkdown(messages, metadata);
        const markdownBlob = new Blob([markdownContent], { type: 'text/markdown;charset=utf-8' });
        saveAs(markdownBlob, `${filename}.md`);
        break;
        
      case 'csv':
        const csvContent = formatAsCSV(messages, metadata);
        const csvBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
        saveAs(csvBlob, `${filename}.csv`);
        break;
        
      case 'pdf':
        const pdf = await generatePDF(messages, metadata);
        pdf.save(`${filename}.pdf`);
        break;
        
      case 'docx':
        const docxBlob = await generateDOCX(messages, metadata);
        saveAs(docxBlob, `${filename}.docx`);
        break;
        
      default:
        throw new Error(`Unsupported format: ${format}`);
    }
  } catch (error) {
    console.error('Error downloading conversation:', error);
    throw error;
  }
}; 