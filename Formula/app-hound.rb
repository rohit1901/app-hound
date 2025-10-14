class AppHound < Formula
  include Language::Python::Virtualenv

  desc "Audit top-level app files and folders on macOS"
  homepage "https://github.com/rohit1901/app-hound"
  url "https://github.com/rohit1901/app-hound/archive/refs/tags/v1.0.2.tar.gz"
  sha256 "c3413aa68d7373169b801158465bcf059a58d43bb2af97e7cc8db6d2e329c2f1"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/app-hound", "--help"
  end
end
