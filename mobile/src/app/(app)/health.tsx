import { Activity } from '@/components/icons';
import { SoonPage } from '@/components/soon';

export default function HealthPage() {
  return (
    <SoonPage
      title="Health" icon={Activity}
      about="How the hub machine in the lab is doing, and how good each robot's connection is."
      needs="The hub doesn't report its own health or keep latency over time yet. Until then, each robot's latency is on the Fleet page."
    />
  );
}
