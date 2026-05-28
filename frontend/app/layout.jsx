import "./globals.css";

export const metadata = {
  title: "MedInsight AI | Clinical Research Interface",
  description: "Clinical research interface for MedInsight AI",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
