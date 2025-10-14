class AppHound < Formula
  include Language::Python::Virtualenv

  desc "Audit top-level app files and folders on macOS"
  homepage "https://github.com/rohit1901/app-hound"
  url "https://github.com/rohit1901/app-hound/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "48affd9f5ed3c379911c92dab012a0cb7fb746b4408a2fb9238bef983156cfd0"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/app-hound", "--help"
  end
end
