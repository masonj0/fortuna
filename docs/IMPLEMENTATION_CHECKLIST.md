# 🚀 Implementation Checklist - Fortuna Improvements

## 🔥 PRIORITY 0 - Critical Fixes (Do First!)

### 1. Fix Missing Import in AtTheRacesAdapter
**Problem**: Line 98 uses `re.search()` but `import re` is missing
**Impact**: 🔥🔥🔥 Critical - Adapter crashes at runtime
**Effort**: 5 minutes
**File**: `python_service/adapters/at_the_races_adapter.py`

```bash
# Quick fix:
# Add this line at the top of at_the_races_adapter.py:
import re
```

**Test**:
```bash
python -c "from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter; print('✅ Import works')"
```

---

## 🎯 PRIORITY 1 - High Impact Upgrades (Do This Week)

### 2. Implement SmartFetcher
**Problem**: Single browser engine, no failover
**Impact**: 🔥🔥🔥 High - Increases reliability by 3x
**Effort**: 2-3 hours
**Files**:
- Create: `python_service/core/smart_fetcher.py`
- Modify: `python_service/adapters/base_adapter_v3.py`

**Steps**:
1. Copy `smart_fetcher.py` to your project
2. Update `BaseAdapterV3.make_request()` to use SmartFetcher
3. Add cleanup method to OddsEngine
4. Test with one adapter first (SportingLife recommended)

**Test**:
```bash
pytest tests/test_smart_fetcher.py -v
```

### 3. Add Browser Availability Detection
**Problem**: CI doesn't know which browsers are available
**Impact**: 🔥🔥 Medium - Prevents errors from missing browsers
**Effort**: 30 minutes
**Files**:
- Use: `verify_browsers_ENHANCED.py`
- Modify: `.github/workflows/unified-race-report.yml` (already done!)

**Steps**:
1. Replace your `verify_browsers.py` with the enhanced version
2. SmartFetcher automatically reads `CAMOUFOX_AVAILABLE` env var
3. Test locally and in CI

**Test**:
```bash
python scripts/verify_browsers.py
cat browser_verification.json | jq '.recommendations'
```

### 4. Enhanced Error Context & Debug Snapshots
**Problem**: Hard to debug scraper failures
**Impact**: 🔥🔥 Medium - Saves hours of debugging
**Effort**: 1 hour
**Files**:
- Modify: Adapter `_fetch_data()` methods

**Steps**:
1. Add `_should_save_debug_html()` method (see fixed adapter)
2. Save HTML on errors to `debug-output/` directory
3. Upload in CI artifacts (already configured!)

**Test**:
```bash
# Force an error and check debug output
DEBUG_MODE=true python scripts/fortuna_reporter.py
ls debug-output/*.html
```

---

## 📈 PRIORITY 2 - Performance Upgrades (Do Next Week)

### 5. Connection Pooling
**Impact**: 🔥 Low-Medium - 10-20% speed improvement
**Effort**: 3 hours
**Status**: Design ready in IMPROVEMENTS.md

### 6. Adaptive Rate Limiting
**Impact**: 🔥 Low - Better handling of rate limits
**Effort**: 2 hours
**Status**: Design ready in IMPROVEMENTS.md

### 7. Circuit Breaker Pattern
**Impact**: 🔥 Low-Medium - Prevent cascading failures
**Effort**: 2 hours
**Status**: Design ready in IMPROVEMENTS.md

---

## 🔬 PRIORITY 3 - Monitoring & Observability (Do Later)

### 8. Structured Logging
**Impact**: 🔥 Low - Better debugging in production
**Effort**: 2 hours
**Status**: Design ready in IMPROVEMENTS.md

### 9. Adapter Health Dashboard
**Impact**: 🔥 Low - Visibility into adapter performance
**Effort**: 4 hours
**Status**: Future work

---

## 📋 Daily Implementation Schedule

### Day 1 (30 minutes)
- [ ] Fix missing `import re` in AtTheRacesAdapter
- [ ] Test fix locally
- [ ] Commit and push

### Day 2 (2 hours)
- [ ] Create `python_service/core/smart_fetcher.py`
- [ ] Update `BaseAdapterV3.make_request()`
- [ ] Test with SportingLife adapter

### Day 3 (1 hour)
- [ ] Add `_configure_fetch_strategy()` to 3-4 adapters
- [ ] Test each adapter individually
- [ ] Monitor health reports

### Day 4 (1 hour)
- [ ] Replace `verify_browsers.py` with enhanced version
- [ ] Test in CI
- [ ] Verify recommendations are helpful

### Day 5 (1 hour)
- [ ] Add debug HTML snapshots to adapters
- [ ] Test error scenarios
- [ ] Review CI artifacts

---

## 🧪 Testing Strategy

### Unit Tests
```bash
# Test SmartFetcher
pytest tests/test_smart_fetcher.py -v

# Test individual adapters
pytest tests/test_sporting_life_adapter.py -v
pytest tests/test_at_the_races_adapter.py -v
```

### Integration Tests
```bash
# Test full pipeline
python scripts/fortuna_reporter.py --date=2024-01-26

# Check outputs
ls -lh qualified_races.json
python scripts/validate_output.py
```

### CI Tests
```bash
# Trigger workflow manually
gh workflow run unified-race-report.yml \
  --ref main \
  -f run_mode=full \
  -f debug_mode=true

# Check results
gh run list --workflow=unified-race-report.yml
gh run view --log
```

---

## 🎯 Success Metrics

Track these before and after:

| Metric | Before | After (Target) |
|--------|--------|----------------|
| Adapter Success Rate | ~85% | >95% |
| CI Failure Rate | ~10% | <2% |
| Average Runtime | 15-20 min | 12-15 min |
| Debug Time per Error | 1-2 hours | 15-30 min |
| Browser Availability | Single engine | 3 engines |

---

## 🔄 Rollback Procedures

### If SmartFetcher Causes Issues
```python
# In base_adapter_v3.py, revert make_request to:
async def make_request(self, method: str, url_path: str, **kwargs):
    async with httpx.AsyncClient() as client:
        response = await client.request(method, url_path, **kwargs)
        return response
```

### If Browser Verification Breaks
```bash
# Revert to simple version
git checkout HEAD~1 scripts/verify_browsers.py
```

---

## 📞 Getting Help

### If you encounter issues:

1. **Check logs**: `cat reporter_output.log`
2. **Check health**: `cat browser_verification.json | jq`
3. **Check artifacts**: Download from GitHub Actions
4. **Debug locally**: `DEBUG_MODE=true python scripts/fortuna_reporter.py`

### Common Issues:

**Issue**: "AsyncStealthySession not available"
**Fix**: `pip install camoufox` (optional, SmartFetcher will use Playwright)

**Issue**: "All engines failed"
**Fix**: Check `browser_verification.json` recommendations

**Issue**: "No races found"
**Fix**: Check `debug-output/*.html` for HTML snapshots

---

## ✅ Definition of Done

For each priority level, consider it done when:

- [ ] Code implemented and tested locally
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] CI tests pass (at least 2 consecutive runs)
- [ ] Documentation updated
- [ ] Rollback procedure verified
- [ ] Team notified of changes

---

## 🎓 Learning Resources

- **Scrapling Docs**: https://github.com/Xyfalix/scrapling
- **Playwright Docs**: https://playwright.dev/python/docs/intro
- **Your IMPROVEMENTS.md**: Detailed implementation guide
- **Your INTEGRATION_GUIDE.md**: Step-by-step SmartFetcher setup

---

**Last Updated**: 2024-01-26
**Next Review**: After Priority 1 items complete
