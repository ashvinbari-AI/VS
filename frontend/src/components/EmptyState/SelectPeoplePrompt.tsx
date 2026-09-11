import { Users } from "lucide-react";
import { EmptyState } from "./EmptyState";

export function SelectPeoplePrompt() {
  return (
    <EmptyState
      icon={<Users size={26} />}
      title="Select Person A and Person B"
      message="Choose both people in the header above to compare their social media activity. Configure new people under Data Sources."
    />
  );
}
