/**
 * PDF Parser using pdf.js
 * Extracts text content from PDF files
 */

export interface PDFParseResult {
  text: string;
  pageCount: number;
  metadata?: Record<string, unknown>;
}

/**
 * Extracts text from a PDF file
 */
export async function parsePDF(file: File): Promise<PDFParseResult> {
  // Only run on client side
  if (typeof window === 'undefined') {
    throw new Error('PDF parsing can only be done on the client side');
  }

  try {
    // Dynamic import to avoid SSR issues
    const pdfjsLib = await import('pdfjs-dist');

    // Set worker path after loading
    pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;

    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

    const pageCount = pdf.numPages;
    const textPages: string[] = [];

    // Extract text from each page
    for (let i = 1; i <= pageCount; i++) {
      const page = await pdf.getPage(i);
      const textContent = await page.getTextContent();

      // Combine text items with spaces
      const pageText = textContent.items
        .map((item: any) => item.str)
        .join(' ');

      textPages.push(pageText);
    }

    // Get PDF metadata
    const metadata = await pdf.getMetadata();

    return {
      text: textPages.join('\n\n'),
      pageCount,
      metadata: metadata.info as Record<string, unknown>,
    };
  } catch (error) {
    throw new Error(`Failed to parse PDF: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Validates if a file is a PDF
 */
export function isPDF(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}
