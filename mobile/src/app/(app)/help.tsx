import { CircleHelp } from '@/components/icons';
import { SoonPage } from '@/components/soon';

export default function HelpPage() {
  return (
    <SoonPage
      title="Help" icon={CircleHelp}
      about="Short articles on how the system works."
      needs="The articles aren't written yet. The one rule that matters most: the red Stop always works, for everyone, on every screen."
    />
  );
}
