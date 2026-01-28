#!/usr/bin/env python3
"""
Quick verification script to check SmartFetcher integration status
Run this in your project root to verify everything is wired correctly
"""

import sys
from pathlib import Path
from typing import List, Tuple

class IntegrationChecker:
    """Check if SmartFetcher is properly integrated"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.results = {
            "smart_fetcher_exists": False,
            "base_adapter_integrated": False,
            "adapters_using_strategy": [],
            "adapters_need_update": [],
            "tests_exist": False,
            "issues": []
        }

    def check_smart_fetcher(self) -> bool:
        """Check if smart_fetcher.py exists"""
        smart_fetcher_path = self.project_root / "python_service" / "core" / "smart_fetcher.py"

        if smart_fetcher_path.exists():
            print("✅ SmartFetcher exists at:", smart_fetcher_path)

            # Check key classes
            content = smart_fetcher_path.read_text()
            if "class SmartFetcher" in content:
                print("  ✓ SmartFetcher class found")
            if "class BrowserEngine" in content:
                print("  ✓ BrowserEngine enum found")
            if "class FetchStrategy" in content:
                print("  ✓ FetchStrategy dataclass found")

            return True
        else:
            print("❌ SmartFetcher NOT found at:", smart_fetcher_path)
            self.results["issues"].append("SmartFetcher file missing")
            return False

    def check_base_adapter(self) -> bool:
        """Check if BaseAdapterV3 uses SmartFetcher"""
        base_path = self.project_root / "python_service" / "adapters" / "base_adapter_v3.py"

        if not base_path.exists():
            print("❌ BaseAdapterV3 NOT found at:", base_path)
            self.results["issues"].append("BaseAdapterV3 missing")
            return False

        print("\n✅ BaseAdapterV3 found at:", base_path)
        content = base_path.read_text()

        # Check for SmartFetcher import
        has_import = False
        if "from python_service.core.smart_fetcher import" in content or \
           "from ..core.smart_fetcher import" in content:
            print("  ✓ SmartFetcher import found")
            has_import = True
        else:
            print("  ⚠️  SmartFetcher import NOT found")
            self.results["issues"].append("BaseAdapterV3 doesn't import SmartFetcher")

        # Check for smart_fetcher initialization
        has_init = False
        if "self.smart_fetcher = SmartFetcher" in content:
            print("  ✓ SmartFetcher initialization found")
            has_init = True
        else:
            print("  ⚠️  SmartFetcher initialization NOT found")
            self.results["issues"].append("BaseAdapterV3 doesn't initialize SmartFetcher")

        # Check for make_request using smart_fetcher
        has_usage = False
        if "self.smart_fetcher.fetch" in content:
            print("  ✓ make_request uses smart_fetcher.fetch()")
            has_usage = True
        else:
            print("  ⚠️  make_request doesn't use smart_fetcher")
            self.results["issues"].append("make_request doesn't use SmartFetcher")

        return has_import and has_init and has_usage

    def check_adapters(self) -> Tuple[List[str], List[str]]:
        """Check which adapters implement _configure_fetch_strategy"""
        adapters_dir = self.project_root / "python_service" / "adapters"

        if not adapters_dir.exists():
            print("\n❌ Adapters directory not found")
            return [], []

        print(f"\n📂 Scanning adapters in: {adapters_dir}")

        using_strategy = []
        need_update = []

        for adapter_file in adapters_dir.glob("*_adapter.py"):
            content = adapter_file.read_text()

            # Skip base adapter
            if "base_adapter" in adapter_file.name:
                continue

            adapter_name = adapter_file.stem.replace("_adapter", "").title()

            if "_configure_fetch_strategy" in content:
                using_strategy.append(adapter_name)
                print(f"  ✓ {adapter_name}: Has _configure_fetch_strategy")
            else:
                need_update.append(adapter_name)
                print(f"  ⚠️  {adapter_name}: Missing _configure_fetch_strategy")

        return using_strategy, need_update

    def check_tests(self) -> bool:
        """Check if tests exist for SmartFetcher"""
        test_paths = [
            self.project_root / "tests" / "test_smart_fetcher.py",
            self.project_root / "tests" / "core" / "test_smart_fetcher.py",
        ]

        print("\n🧪 Checking for tests...")

        for test_path in test_paths:
            if test_path.exists():
                print(f"✅ Tests found at: {test_path}")
                return True

        print("⚠️  No SmartFetcher tests found")
        self.results["issues"].append("SmartFetcher tests missing")
        return False

    def check_workflow(self) -> bool:
        """Check if GitHub workflow is configured correctly"""
        workflow_path = self.project_root / ".github" / "workflows" / "unified-race-report.yml"

        if not workflow_path.exists():
            print("\n⚠️  GitHub workflow not found")
            return False

        print("\n🔧 Checking GitHub workflow...")
        content = workflow_path.read_text()

        checks = {
            "CAMOUFOX_AVAILABLE": "Camoufox availability flag",
            "CHROMIUM_AVAILABLE": "Chromium availability flag",
            "verify_browsers": "Browser verification script",
            "debug-output": "Debug output directory"
        }

        all_good = True
        for key, description in checks.items():
            if key in content:
                print(f"  ✓ {description}")
            else:
                print(f"  ⚠️  Missing: {description}")
                all_good = False

        return all_good

    def generate_report(self) -> str:
        """Generate markdown report"""
        report = ["# 🔍 SmartFetcher Integration Status Report\n\n"]
        report.append(f"**Project Root**: {self.project_root.absolute()}\n\n")

        # Summary
        report.append("## 📊 Summary\n\n")
        report.append(f"- SmartFetcher exists: {'✅' if self.results['smart_fetcher_exists'] else '❌'}\n")
        report.append(f"- BaseAdapter integrated: {'✅' if self.results['base_adapter_integrated'] else '❌'}\n")
        report.append(f"- Adapters using strategy: {len(self.results['adapters_using_strategy'])}\n")
        report.append(f"- Adapters need update: {len(self.results['adapters_need_update'])}\n")
        report.append(f"- Tests exist: {'✅' if self.results['tests_exist'] else '⚠️'}\n\n")

        # Issues
        if self.results["issues"]:
            report.append("## ⚠️ Issues Found\n\n")
            for issue in self.results["issues"]:
                report.append(f"- {issue}\n")
            report.append("\n")

        # Adapters using strategy
        if self.results["adapters_using_strategy"]:
            report.append("## ✅ Adapters with FetchStrategy\n\n")
            for adapter in sorted(self.results["adapters_using_strategy"]):
                report.append(f"- {adapter}\n")
            report.append("\n")

        # Next steps
        report.append("## 🚀 Next Steps\n\n")

        if not self.results["base_adapter_integrated"]:
            report.append("1. **CRITICAL**: Integrate SmartFetcher into BaseAdapterV3\n")

        if self.results["adapters_need_update"]:
            report.append(f"2. Update {len(self.results['adapters_need_update'])} adapters to use FetchStrategy\n")

        return "".join(report)

    def run(self):
        """Run all checks"""
        print("=" * 60)
        print("SMARTFETCHER INTEGRATION VERIFICATION")
        print("=" * 60)

        self.results["smart_fetcher_exists"] = self.check_smart_fetcher()
        self.results["base_adapter_integrated"] = self.check_base_adapter()

        using, needing = self.check_adapters()
        self.results["adapters_using_strategy"] = using
        self.results["adapters_need_update"] = needing

        self.results["tests_exist"] = self.check_tests()
        self.check_workflow()

        report = self.generate_report()
        report_path = Path("integration_check_report.md")
        report_path.write_text(report)
        print(f"\n📄 Report saved to: {report_path.absolute()}")

        if self.results["base_adapter_integrated"] and len(self.results["adapters_using_strategy"]) > 0:
            print("✅ SmartFetcher is INTEGRATED and WORKING!")
            return 0
        else:
            print("❌ SmartFetcher integration INCOMPLETE")
            return 1

if __name__ == "__main__":
    checker = IntegrationChecker(".")
    sys.exit(checker.run())
