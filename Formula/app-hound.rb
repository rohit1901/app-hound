class AppHound < Formula
  include Language::Python::Virtualenv

  desc "Audit top-level app files and folders on macOS"
  homepage "https://github.com/rohit1901/app-hound"
  url "https://github.com/rohit1901/app-hound/archive/refs/tags/v0.2.6.tar.gz"
  sha256 "d486506bbfe81018ca622e77e08de0dc6140647d3bf4ea515320b9719405a1cd"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/app-hound", "--help"
  end
end
