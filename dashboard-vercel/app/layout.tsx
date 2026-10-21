import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata={title:'Spotify · Review Evidence',description:'From original Spotify reviews to traceable product priorities. Saved data, independent checks, and grounded recommendations.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
