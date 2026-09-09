build_lib(
  LIBNAME cqra
  SOURCE_FILES model/calibrated-quantile-wifi-manager.cc
               model/ors-wifi-manager.cc
  HEADER_FILES model/calibrated-quantile-wifi-manager.h
               model/ors-wifi-manager.h
  LIBRARIES_TO_LINK ${libcore} ${libnetwork} ${libwifi}
)
