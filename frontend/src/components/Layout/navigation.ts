import type { LucideIcon } from "lucide-react";
import {
  Activity, BarChart3, Users, MessageSquare, FileText, Compass,
  Clock, Database, Settings as SettingsIcon, TrendingUp, Smile, Search, ClipboardCheck,
  FileBarChart,
} from "lucide-react";

/** One sidebar entry + the title/description shown at the top of its page.
 * Single source of truth for both the Sidebar and the Header's page title,
 * so a page's name never drifts between the two. */
export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Shown under the page title in the header. */
  description: string;
  /** Whether this page compares the selected people -- if false, the
   * people picker + filter bar are hidden (they'd do nothing there). */
  comparison: boolean;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Dashboard",
    items: [
      { to: "/overview", label: "Overview", icon: BarChart3, comparison: true,
        description: "Headline numbers and trends for everyone you're comparing." },
      { to: "/comparison", label: "Head-to-Head", icon: Users, comparison: true,
        description: "Every metric side by side, with the leader of each one." },
      { to: "/report", label: "Report", icon: FileBarChart, comparison: true,
        description: "A complete printable summary -- download it as a PDF." },
    ],
  },
  {
    title: "Analysis",
    items: [
      { to: "/activity", label: "Activity", icon: Activity, comparison: true,
        description: "How often and when each person posts." },
      { to: "/engagement", label: "Engagement", icon: TrendingUp, comparison: true,
        description: "The best-performing posts and reels." },
      { to: "/content", label: "Content Mix", icon: FileText, comparison: true,
        description: "What kinds of content each person publishes." },
      { to: "/narratives", label: "Narratives", icon: Compass, comparison: true,
        description: "The themes each person's posts focus on (model-classified)." },
      { to: "/sentiment", label: "Sentiment", icon: Smile, comparison: true,
        description: "How the audience reacts in comments (model-classified)." },
      { to: "/comments", label: "Comments & Issues", icon: MessageSquare, comparison: true,
        description: "Comment volume, themes, and the public issues people raise." },
    ],
  },
  {
    title: "Browse",
    items: [
      { to: "/timeline", label: "Timeline", icon: Clock, comparison: true,
        description: "Every post in date order." },
      { to: "/explorer", label: "Content Explorer", icon: Search, comparison: true,
        description: "Search and filter individual posts." },
    ],
  },
  {
    title: "Manage",
    items: [
      { to: "/data-sources", label: "Data Sources", icon: Database, comparison: false,
        description: "Add people, scrape or import their data, and run analysis." },
      { to: "/evaluation", label: "Evaluation", icon: ClipboardCheck, comparison: false,
        description: "Check the app's numbers and classifications against verified data." },
      { to: "/settings", label: "Settings", icon: SettingsIcon, comparison: false,
        description: "Theme, date format, NLP options and demo mode." },
    ],
  },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items.map((item) => ({ ...item, group: g.title })));

/** Metadata for the current route; sub-routes (e.g. /sentiment/detail)
 * resolve to their parent page. */
export function routeMeta(pathname: string): (NavItem & { group: string }) | undefined {
  return ALL_ITEMS.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
}
