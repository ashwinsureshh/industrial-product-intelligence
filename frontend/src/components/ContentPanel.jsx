export default function ContentPanel({ content }) {
  if (!content) return null

  return (
    <div className="card">
      <div className="card-head">
        <h3>Commerce Content</h3>
        <div className="spacer" />
        <span className="pill">{content.title.length} / 150 title chars</span>
      </div>

      <div className="card-body">
        <div className="content-block">
          <div className="content-label">Product Title</div>
          <div className="content-title">{content.title}</div>
        </div>

        <div className="content-block">
          <div className="content-label">Short Description</div>
          <div className="content-text">{content.short_description}</div>
        </div>

        <div className="content-block">
          <div className="content-label">Long Description</div>
          <div className="content-text">{content.long_description}</div>
        </div>

        {content.bullets?.length > 0 && (
          <div className="content-block">
            <div className="content-label">Key Specifications</div>
            <ul className="bullets">
              {content.bullets.map((bullet, index) => (
                <li key={index}>{bullet}</li>
              ))}
            </ul>
          </div>
        )}

        {content.meta_description && (
          <div className="content-block">
            <div className="content-label">
              Meta Description
              <span style={{ color: content.meta_description.length > 158 ? 'var(--error)' : 'var(--text-3)' }}>
                {content.meta_description.length} / 158
              </span>
            </div>
            <div className="content-text">{content.meta_description}</div>
          </div>
        )}

        {content.keywords?.length > 0 && (
          <div className="content-block">
            <div className="content-label">Keywords</div>
            <div className="tag-row">
              {content.keywords.map((keyword) => (
                <span className="pill" key={keyword}>
                  {keyword}
                </span>
              ))}
            </div>
          </div>
        )}

        {content.search_terms?.length > 0 && (
          <div className="content-block">
            <div className="content-label">Search Synonyms</div>
            <div className="tag-row">
              {content.search_terms.map((term) => (
                <span className="pill" key={term}>
                  {term}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
