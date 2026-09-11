// Mirrors backend/app/models/common.py -- every API call returns this shape.
export interface ApiError {
  code: string;
  message: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface PersonConfig {
  id: string;
  name: string;
  instagram_url: string | null;
  facebook_url: string | null;
  instagram_profile_key: string | null;
  facebook_profile_key: string | null;
  created_at: string;
  updated_at: string;
  notes: string | null;
}

// Mirrors backend/app/models/content.py NormalizedContent. Any field the
// scraper doesn't provide is null -- render as "N/A", never fabricate.
export interface ContentItem {
  person_id: string;
  person_name: string;
  platform: "instagram" | "facebook";
  content_id: string;
  content_type: "post" | "reel" | "video" | "photo" | "text" | "unknown";
  content_url: string | null;
  published_at: string | null;
  published_at_local: string | null;
  caption: string | null;
  likes: number | null;
  comments_count: number | null;
  shares: number | null;
  reactions_total: number | null;
  reactions_breakdown: Record<string, number> | null;
  view_count: number | null;
  followers_at_collection: number | null;
  hashtags: string[];
  mentions: string[];
  media_url: string | null;
  media_urls: string[] | null;
  author: string | null;
  raw_source_file: string;
  raw_record_id: string;
  scraped_at: string | null;
  last_run_id: string | null;
  engagement: number | null;
  narrative: string | null;
  narrative_confidence: number | null;
  sentiment: string | null;
  sentiment_confidence: number | null;
  nlp_model: string | null;
}

export interface CommentItem {
  person_id: string;
  person_name: string;
  platform: "instagram" | "facebook";
  content_id: string;
  comment_id: string;
  author_username: string | null;
  author_profile_url: string | null;
  comment_text: string | null;
  commented_at: string | null;
  like_count: number | null;
  reply_count: number | null;
  status: string | null;
  sentiment: string | null;
  theme: string | null;
  issues: string[];
}

export interface GlobalFilters {
  personA: string;
  personB: string;
  platform: "all" | "instagram" | "facebook";
  contentType: "all" | "post" | "reel" | "video" | "photo";
  dateFrom: string | null;
  dateTo: string | null;
  periodDays: number;
}
