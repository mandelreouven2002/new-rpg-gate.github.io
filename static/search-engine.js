/**
 * SearchEngine - Pure Logic Class
 * Handles normalization, filtering, region expansion, and scoring.
 * Zero DOM manipulation here.
 */
class SearchEngine {
    constructor(data, regions) {
        this.data = data || [];
        this.regions = regions || [];
    }

    /**
     * Updates the dataset if needed dynamically
     */
    setData(data) {
        this.data = data;
    }

    /**
     * Normalizes Hebrew text for loose matching.
     */
    normHeb(s) {
        return (s || '')
            .toLowerCase()
            .replace(/[\u200E\u200F\u202A-\u202E]/g, '')
            .replace(/[-–—]/g, ' ')
            .replace(/[“”"׳׳״'`.,;:!?()[\]{}<>\\/|]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    /**
     * Extracts types/tags from an item.
     */
    getItemTypes(item) {
        const types = [];
        if (Array.isArray(item.type)) types.push(...item.type);
        else if (typeof item.type === 'string') types.push(item.type);

        if (Array.isArray(item.tags)) types.push(...item.tags);
        else if (typeof item.tags === 'string') types.push(item.tags);

        return [...new Set(types)].filter(Boolean);
    }

    /**
     * Determines if region expansion is needed based on query.
     */
    shouldExpandRegion(normQuery) {
        if (!normQuery) return false;

        const parts = normQuery.split(' ').filter(Boolean);
        const hasPrefix = /^(קריית|קרית|קיבוץ|מושב|כפר|בית|מעלה)\b/i.test(normQuery);

        if (hasPrefix || parts.length >= 2) return true;
        if (normQuery.length < 2) return false;

        return this.regions.some(r =>
            (r.settlements || []).some(s => {
                const normS = this.normHeb(s);
                // Allow includes for longer words (>=3 chars)
                if (normQuery.length >= 3) return normS.includes(normQuery);
                return normS.startsWith(normQuery);
            })
        );
    }

    /**
     * THE MAIN ALGORITHM
     * Returns a sorted array of items based on query and filter.
     */
    search(rawQuery, filterType = 'all') {
        const query = this.normHeb(rawQuery);
        let results = this.data;

        // 1. Filter by Type
        if (filterType !== 'all') {
            results = results.filter(item => this.getItemTypes(item).includes(filterType));
        }

        // If no query, return filtered list as is (shuffled/ordered by default)
        if (!query) {
            return results;
        }

        // 2. Prepare Smart Context (Regions & Siblings)
        const allowRegionExpand = this.shouldExpandRegion(query);

        const regionsMatchingQuery = (allowRegionExpand) ? this.regions.filter(region => {
            const rName = this.normHeb(region.name);
            const regionNameMatch = rName.includes(query);

            const settlementMatch = (region.settlements || []).some(s => {
                const ss = this.normHeb(s);
                if (!ss) return false;
                if (query.length >= 3) return ss.includes(query);
                return ss.startsWith(query);
            });

            return regionNameMatch || settlementMatch;
        }) : [];

        // Gather siblings (neighboring settlements)
        const stopKeywords = new Set(['דן']);
        const regionKeywords = regionsMatchingQuery.flatMap(r => (r.settlements || []).map(s => this.normHeb(s)));
        const uniqueKeywords = [...new Set(regionKeywords)]
            .filter(k => k && k.length >= 2 && !stopKeywords.has(k));

        // Gather direct settlement matches (for partial match safety)
        let settlementsContainingQuery = [];
        if (query.length > 1) {
            settlementsContainingQuery = this.regions.flatMap(r =>
                (r.settlements || []).map(s => this.normHeb(s)).filter(s => s.includes(query))
            );
        }

        // 3. Score & Sort
        return results
            .map(item => {
                let score = 0;
                const nameL = this.normHeb(item.name);
                const descL = this.normHeb(item.description);
                const locL  = this.normHeb(item.location);

                // Direct Matches
                if (nameL.includes(query)) score += 50;
                if (descL.includes(query)) score += 20;
                if (locL.includes(query)) score += 30;

                // Region Name Match
                if (regionsMatchingQuery.length > 0 && locL) {
                    const isRegionNameMatch = regionsMatchingQuery.some(r => locL.includes(this.normHeb(r.name)));
                    if (isRegionNameMatch) score += 40;
                }

                // Sibling Logic (Smart Context)
                if (uniqueKeywords.length > 0 && locL) {
                    const isSiblingMatch = uniqueKeywords.some(k => locL.includes(k) || k.includes(locL));
                    if (isSiblingMatch) score += 10;
                }

                // Direct Settlement Logic
                if (settlementsContainingQuery.length > 0 && locL) {
                    const matchesSpecificSettlement = settlementsContainingQuery.some(s => locL.includes(s));
                    if (matchesSpecificSettlement) score += 10;
                }

                return { item, score };
            })
            .filter(entry => entry.score > 0)
            .sort((a, b) => b.score - a.score)
            .map(entry => entry.item);
    }
}
