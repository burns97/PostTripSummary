# Google Stitch Design Prompt

## Product Overview

Design a complete web-based SaaS application called **"TripStory"** — a trip storytelling platform that transforms vacation photos into beautiful, shareable trip narratives. Users upload their photos, the system automatically organizes them into a day-by-day timeline with named events, AI-generated descriptions, and a curated highlight reel. The user reviews and edits the draft, picks a visual theme, and shares it as a beautiful interactive web page or downloadable PDF.

**Core value prop:** "Drop your photos. Get your story." — Zero effort trip documentation that looks like a professional travel blog.

**Design language:** Modern, warm, editorial. Think Airbnb meets Medium meets Apple Photos. Clean typography, generous whitespace, photo-forward layouts. The UI should feel like a premium travel magazine, not a developer tool.

**Color palette suggestion:** Warm neutrals (cream, sand, warm gray) with a single accent color (deep teal or terracotta). Photos should be the hero — the UI frames them, never competes with them.

---

## Pages & Screens to Design

### 1. Landing Page / Marketing

A conversion-focused landing page for new visitors.

**Sections:**
- **Hero:** Full-bleed vacation photo background with overlay text: "Turn your vacation photos into a beautiful travel story." CTA button: "Create Your First Story — Free". Secondary CTA: "See an example"
- **How It Works:** Three-step illustration strip: (1) Upload your photos (drag-and-drop illustration), (2) We organize your story (timeline building animation), (3) Share with everyone (sharing icons). Keep it visual, minimal text.
- **Example Story:** An embedded interactive preview of a sample trip story (e.g., "Sarah's Iceland Adventure — 7 days, 12 stops, 340 photos → 1 beautiful story"). Show the actual output format so users know what they'll get.
- **Feature highlights:** Cards for key features: AI-powered descriptions, automatic photo curation, multiple sharing formats (web link, PDF, blog embed), collaborative editing, privacy controls
- **Pricing section:** Three tiers displayed as cards:
  - **Free:** 1 trip, up to 200 photos, basic themes, watermarked PDF
  - **Explorer ($5/month):** Unlimited trips, 1000 photos per trip, all themes, no watermark, custom domain sharing
  - **Adventurer ($12/month):** Everything in Explorer + collaborative trips, priority AI processing, API access, bulk export
- **Social proof:** Testimonial cards with user photos and trip thumbnails. "I used to spend hours making photo albums. Now I just upload and share." Stats: "50,000+ stories created"
- **Footer:** Links to About, Blog, Privacy Policy, Terms, Support, Social media icons

### 2. Authentication

**Sign Up page:**
- Email + password form with password strength indicator
- "Continue with Google" and "Continue with Apple" OAuth buttons (prominent, above the email form)
- "Already have an account? Sign in" link
- Clean, centered card layout with a blurred travel photo background

**Sign In page:**
- Email + password with "Forgot password?" link
- Same OAuth buttons
- "Don't have an account? Create one free" link

**Forgot Password page:**
- Email input, "Send reset link" button, success confirmation state

### 3. Dashboard (Trip List)

The user's home screen after login. Shows all their trips.

**Layout:**
- **Top nav bar:** TripStory logo (left), search bar (center), notification bell + user avatar with dropdown (right)
- **Welcome section:** "Welcome back, Matt" with a "Create New Trip" prominent button (+ icon)
- **Trip grid:** Card-based grid (responsive: 3 columns on desktop, 2 on tablet, 1 on mobile). Each trip card shows:
  - Cover photo (the top-scored highlight photo, or user-selected)
  - Trip name (editable on click)
  - Date range (e.g., "Mar 5–12, 2026")
  - Location summary (e.g., "Iceland · 7 days · 12 stops")
  - Status badge: "Draft" (yellow), "Published" (green), "Processing" (blue with spinner)
  - Quick actions on hover: Edit, Share, Duplicate, Delete
  - Collaborator avatars (small circles) if shared trip
- **Empty state:** Illustration of a camera with text "No trips yet. Upload some photos to create your first story!" with CTA button
- **Filter/sort bar:** Filter by status (All, Drafts, Published), sort by date (newest first, oldest first)
- **Sidebar (collapsible):**
  - My Trips
  - Shared With Me
  - Templates
  - Connected Accounts (Google Maps, Apple Health, Day One)
  - Settings
  - Subscription & Billing

### 4. New Trip Creation Flow

A multi-step wizard that feels lightweight, not bureaucratic.

**Step 1: Upload Photos**
- Large drag-and-drop zone (dashed border, camera icon) center screen
- "Drag photos here or click to browse" text
- Support for folders (drag entire folder)
- Upload progress: grid of photo thumbnails filling in as they upload, with a progress bar and count ("Uploading 247 of 340 photos...")
- "Continue" button activates once at least 10 photos are uploaded
- Small text: "Supported: JPEG, PNG, HEIC. We'll extract dates and locations from your photo metadata."

**Step 2: Trip Details (optional, auto-detected)**
- Trip name field (pre-filled from date range and detected location: "Iceland, March 2026")
- Date range (auto-detected from photo timestamps, editable with date picker)
- Cover photo selector (shows top 6 auto-scored photos as options, click to select, or "Choose from all photos")
- "Add more data sources (optional)" expandable section:
  - **Google Maps Timeline:** "Connect Google" button → OAuth flow → date range auto-filter → shows preview of matched locations
  - **Itinerary:** File drop zone for Excel/CSV with text "Upload your hotel bookings, flight details, or activity reservations"
  - **Expenses:** File drop zone for credit card CSV with text "Add spending data to see cost breakdowns"
  - **Journal Entries:** "Connect Day One" button or file upload for JSON export
  - **Health Data:** "Connect Apple Health" or file upload
  - Each connected source shows a green checkmark and count (e.g., "✓ 23 locations matched")
- "Create Story" button

**Step 3: Processing Screen**
- Full-screen processing view with stages shown as a vertical progress timeline:
  1. "Reading your photos..." (spinner → checkmark) — shows count: "Found 340 photos across 7 days"
  2. "Identifying locations..." (spinner) — shows mini-map with pins appearing
  3. "Organizing your timeline..." (spinner) — shows day cards fading in
  4. "Writing descriptions..." (spinner) — shows text snippets appearing
  5. "Curating highlights..." (spinner) — shows photo grid with gold borders appearing
  6. "Building your story..." (spinner → checkmark)
- Estimated time remaining: "About 2 minutes left"
- Fun travel facts or tips shown while waiting (rotating): "Did you know? The average vacation produces 500+ photos but only 50 make it into a shared album."
- "We'll email you when it's ready" option for large trips
- On completion: celebratory micro-animation, then auto-redirect to editor

### 5. Trip Editor (Core Experience)

This is the main product screen — where users review and customize their auto-generated trip story. It should feel like editing a document in Notion or a story in Medium, not like using a photo management tool.

**Layout: Three-panel design**

**Left Panel — Day Navigator (narrow, ~200px):**
- Vertical list of days: "Day 1 — Mar 5", "Day 2 — Mar 6", etc.
- Each day shows: event count, photo count, small thumbnail
- Click to scroll main panel to that day
- Current day highlighted
- Collapse/expand toggle

**Center Panel — Story Editor (main, scrollable):**
- **Trip Header:**
  - Large cover photo (click to change)
  - Trip title (editable, large font)
  - Subtitle: date range + location summary (editable)
  - "By Matt" with avatar (links to profile)

- **Day Sections:** Each day is a distinct section with:
  - Day header: "Day 3 — Thursday, March 7" with weather icon (if available) and total stats
  - Day summary (AI-generated 1-2 sentence overview, editable as rich text)

- **Event Cards:** Within each day, events are shown as content blocks:
  - **Event name** (large, editable) with type icon (🏛️ landmark, 🍽️ restaurant, 🏨 hotel, 🎯 activity, 🚌 transit)
  - **Time range** (e.g., "2:30 PM – 4:15 PM") — editable
  - **Location** shown as a subtle map pin with place name — click opens small inline map
  - **Photo strip:** Horizontal scrollable row of photos for this event
    - Highlight photos have a subtle gold border/star badge
    - Click photo to expand to lightbox view
    - Drag to reorder
    - Right-click or long-press for menu: "Set as highlight", "Remove from story", "Set as cover"
    - "Add photos" button at end of strip to add from unused photos
  - **Description** (AI-generated paragraph, editable as rich text with formatting toolbar)
  - **Notes field** (optional, user-added, shown as a subtle blockquote or aside)
  - **Source badges** (small, muted): icons showing where data came from (camera, Google Maps, itinerary, credit card)
  - **Event actions** (shown on hover): Merge with adjacent event, Split event, Change type, Delete event
  - Drag handle on left edge to reorder events within a day

- **Between events:** A subtle "+" button to manually add an event or note

- **Expense Summary** (collapsible section at bottom of each day):
  - Small table: merchant, category, amount
  - Day total

- **Trip Footer:**
  - "By the Numbers" stats block: X days, X stops, X photos, X countries, X cities
  - Total expenses breakdown (if expense data provided)
  - Mini route map

**Right Panel — Properties & Tools (~280px, collapsible):**
- **Context-sensitive** — changes based on what's selected in the center panel

- **When nothing selected (trip-level):**
  - Trip settings: name, dates, visibility (public/private/unlisted)
  - Theme picker: grid of theme thumbnails (6-8 options): "Classic", "Modern", "Polaroid", "Magazine", "Minimal", "Vintage", "Dark", "Tropical"
  - Cover photo selector
  - Connected data sources (with status indicators)
  - Collaborators section: invite by email, permission levels (editor, viewer)
  - Export options: "Download PDF", "Download HTML", "Get embed code"
  - Danger zone: "Delete trip" (with confirmation)

- **When an event is selected:**
  - Event type dropdown
  - Location editor (search box + map)
  - Photo management: grid of all photos in event, toggle highlight/remove
  - Sources list
  - "Regenerate description" button (re-runs AI)

- **When a photo is selected (in lightbox):**
  - Photo metadata: timestamp, camera, location coordinates
  - AI description (editable)
  - Quality score (shown as stars or bar)
  - Actions: Set as highlight, Remove, Set as event cover, Download original

**Toolbar (sticky, top of center panel):**
- Undo / Redo buttons
- "Preview" button (opens the published view in new tab)
- "Regenerate All Descriptions" (with cost indicator: "~$0.03")
- Auto-save indicator: "All changes saved" with timestamp
- "Publish" button (prominent, right-aligned)

### 6. Published Trip View (Shareable Output)

The read-only, public-facing version of a trip story. This is what gets shared via link.

**Design:** Full-width, immersive, editorial layout. No app chrome — just the story.

- **Hero section:** Full-bleed cover photo with trip title overlaid, date range, author name
- **Route map:** Interactive map (Mapbox/Leaflet) showing all event locations with numbered markers. Clicking a marker scrolls to that event.
- **Day-by-day narrative:**
  - Day headers with date
  - Events as content blocks with large photos (hero photo full-width, additional photos in a 2-3 column masonry grid)
  - AI descriptions as body text
  - User notes as styled blockquotes
  - Location names as subtle tags
- **Highlight reel:** Auto-playing carousel of the top 10 highlight photos (optional section, toggleable)
- **Stats footer:** "By the Numbers" section with iconographic stats
- **Expense summary** (only if user opted in to share it)
- **Footer:** "Made with TripStory" branding (removable on paid plans), share buttons (copy link, Twitter/X, Facebook, email), "Create your own trip story" CTA for viral growth
- **Mobile responsive:** Single column, swipeable photo galleries, collapsible day sections

### 7. Theme Preview / Selection

A dedicated screen for choosing and customizing the visual theme.

- **Split view:** Theme options on the left (scrollable grid), live preview on the right
- **Theme cards:** Each shows a small preview of the same trip content rendered in that theme
- **Themes to include:**
  - **Classic:** Clean serif fonts, cream background, traditional photo album feel
  - **Modern:** Sans-serif, white background, generous spacing, magazine-like
  - **Polaroid:** Photos styled as polaroid frames with handwritten-style captions
  - **Magazine:** Bold typography, asymmetric photo layouts, high contrast
  - **Minimal:** Maximum whitespace, very small text, photos dominate
  - **Vintage:** Warm sepia tones, textured paper background, rounded corners
  - **Dark:** Dark background, photos glow, elegant night-mode aesthetic
  - **Tropical:** Bright colors, playful fonts, illustrated borders
- **Customization options** (per theme): accent color picker, font pairing selector (3-4 options per theme), photo corner style (sharp, rounded, polaroid)

### 8. Sharing & Export

**Share modal (triggered from editor or published view):**
- **Link sharing:** Copy link button, visibility toggle (public / unlisted / private), custom slug editor (tripstory.com/matt/iceland-2026)
- **Social sharing:** One-click share buttons for major platforms with auto-generated preview card (OG image from cover photo)
- **Email sharing:** "Send to friends" — email input with comma separation, optional personal message, preview of email that will be sent
- **Embed:** Code snippet for embedding in blog/website (responsive iframe)
- **Export:** Download as PDF (with theme applied), Download as HTML (self-contained), Download photos (ZIP of highlights only or all kept photos)
- **Collaborative link:** "Invite contributors" — generates a link that lets others upload their photos from the same trip to merge into the story

### 9. Settings & Account

**Profile tab:**
- Avatar upload, display name, bio (shown on published stories)
- Email, password change
- Connected social accounts

**Connected Services tab:**
- Google Maps: Connect/disconnect, shows last sync date
- Apple Health: Connect/disconnect
- Day One: Connect/disconnect
- Each shows what data is pulled and privacy note

**Preferences tab:**
- Default AI provider preference (if offering choice)
- Default theme for new trips
- Default visibility (public/private)
- Email notification preferences (processing complete, someone viewed your story, weekly digest)
- Unit preferences (miles/km, Fahrenheit/Celsius)
- Language preference

**Subscription & Billing tab:**
- Current plan with usage stats (trips created this month, storage used)
- Upgrade/downgrade buttons
- Payment method management
- Invoice history
- "Cancel subscription" with retention offer

**Data & Privacy tab:**
- Download all data (GDPR export)
- Delete account (with confirmation and data deletion timeline)
- Photo storage usage bar
- "Delete all trips" option

### 10. Collaborative Trip Editing

When a trip has multiple contributors:

- **Contributor bar** at the top of editor showing active editors (colored avatar dots, like Google Docs)
- **Activity feed** in right panel showing recent changes: "Sarah added 45 photos", "Mike renamed 'Unknown event' to 'Blue Lagoon'"
- **Merge flow:** When a contributor uploads photos, they're added to existing events by timestamp/location match, with a "Review new additions" prompt for the trip owner
- **Permission levels:** Owner (full control), Editor (can edit content, add photos), Viewer (read-only access to draft)
- **Comments:** Inline comments on events or photos (like Google Docs comments) — click to add a comment bubble, reply thread

### 11. Notification Center

Accessed via bell icon in nav:
- "Your Iceland trip is ready to review!" (processing complete)
- "Sarah added 45 photos to Iceland 2026" (collaborator activity)
- "Your Iceland story was viewed 23 times this week" (analytics)
- "Mike left a comment on Blue Lagoon" (collaboration)
- Mark all as read, settings link

### 12. Mobile-Responsive Considerations

The app should be fully responsive. Key mobile adaptations:
- **Dashboard:** Single column trip cards, bottom tab navigation (Home, Create, Shared, Settings)
- **Editor:** Single panel with bottom sheet for properties. Day navigator becomes a horizontal pill bar at the top. Photo strips become swipeable carousels.
- **Upload:** Camera roll integration prompt ("Select from camera roll" in addition to file picker)
- **Published view:** Already full-width, but photo grids become single-column, map becomes smaller with "Expand" option

### 13. Empty & Error States

Design these states too:
- **No trips:** Friendly illustration + "Create your first story" CTA
- **Processing failed:** "We had trouble with some of your photos. 12 photos couldn't be read. Continue with 328 photos?" with retry option
- **No GPS data:** "We couldn't find location data in your photos. Want to add locations manually?" with a map-based event placement tool
- **AI unavailable:** "AI descriptions are temporarily unavailable. Your story has been created without descriptions — we'll add them automatically when service resumes."
- **Upload interrupted:** "You have an unfinished upload (147 of 340 photos). Resume or start over?"
- **Offline indicator:** Subtle banner: "You're offline. Changes will sync when you reconnect."

### 14. Onboarding Flow

First-time user experience after signup:
1. "Welcome to TripStory!" — brief animation showing the product in action (3-4 seconds)
2. "Let's create your first story" — points to upload zone
3. Tooltips on first trip: highlight key features (event editing, photo highlights, theme selection) as contextual popovers, dismissible, "Don't show again" option
4. After first trip is published: celebration animation + "Share your story" prompt + "Rate us" prompt (delayed)

---

## Technical Design Notes for the UI

- **State management:** Real-time auto-save with debounce (save 1 second after last edit). Show "Saving..." → "Saved" indicator.
- **Photo loading:** Lazy-load photos as user scrolls. Show blur-up placeholders (tiny base64 thumbnails that blur-up to full resolution). Serve responsive image sizes (thumbnail, medium, full).
- **Drag and drop:** Use a library like dnd-kit for event reordering and photo management. Show drop zones with visual feedback.
- **Rich text editing:** Use a lightweight editor (Tiptap/ProseMirror) for descriptions and notes. Support bold, italic, links, and blockquotes only — no complex formatting.
- **Map integration:** Mapbox GL JS for interactive maps in published view. Static map images for editor previews and PDF export.
- **Animations:** Subtle, purposeful. Page transitions (fade), card hover effects (lift shadow), processing stage completions (checkmark pop), photo highlight toggle (gold border fade-in). Nothing flashy or distracting.
- **Accessibility:** WCAG 2.1 AA compliance. Keyboard navigation for all actions. Screen reader labels for photos (using AI descriptions). High contrast mode option. Focus indicators on interactive elements.
