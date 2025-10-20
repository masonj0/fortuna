// web_platform/frontend/src/app/page.tsx
import LiveRaceDashboardNoSSR from '../components/LiveRaceDashboardNoSSR';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-4 md:p-12">
      <LiveRaceDashboardNoSSR />
    </main>
  );
}
