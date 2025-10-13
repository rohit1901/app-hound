class AppHound < Formula
  include Language::Python::Virtualenv

  desc "Audit top-level app files and folders on macOS"
  homepage "https://github.com/rohit1901/app-hound"
  url "Tarball URL goes here"
  sha256 "sha256 goes here"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/app-hound", "--help"
  end
end
