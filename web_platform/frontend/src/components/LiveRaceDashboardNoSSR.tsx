// web_platform/frontend/src/components/LiveRaceDashboardNoSSR.tsx
import dynamic from 'next/dynamic';

const LiveRaceDashboardNoSSR = dynamic(
  () => import('./LiveRaceDashboard').then((mod) => mod.LiveRaceDashboard),
  { ssr: false }
);

export default LiveRaceDashboardNoSSR;
