/**
 * DOCX Parser using mammoth.js
 * Extracts text content from DOCX files
 */

import mammoth from 'mammoth';

export interface DOCXParseResult {
  text: string;
  html?: string;
  messages?: string[];
}

/**
 * Extracts text from a DOCX file
 */
export async function parseDOCX(file: File): Promise<DOCXParseResult> {
  try {
    const arrayBuffer = await file.arrayBuffer();

    // Extract text
    const textResult = await mammoth.extractRawText({ arrayBuffer });

    // Optionally extract HTML for better formatting
    const htmlResult = await mammoth.convertToHtml({ arrayBuffer });

    return {
      text: textResult.value,
      html: htmlResult.value,
      messages: textResult.messages.map(m => m.message),
    };
  } catch (error) {
    throw new Error(`Failed to parse DOCX: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Validates if a file is a DOCX
 */
export function isDOCX(file: File): boolean {
  return (
    file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    file.name.toLowerCase().endsWith('.docx')
  );
}
