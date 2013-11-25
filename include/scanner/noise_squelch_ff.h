/* -*- c++ -*- */
/*
 * Copyright 2006,2012 Free Software Foundation, Inc.
 *
 * This file is part of GNU Radio
 *
 * GNU Radio is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 *
 * GNU Radio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with GNU Radio; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef INCLUDED_SCANNER_NOISE_SQUELCH_FF_H
#define INCLUDED_SCANNER_NOISE_SQUELCH_FF_H

#include <scanner/api.h>
#include <gnuradio/analog/squelch_base_ff.h>
#include <cmath>

namespace gr {
  namespace scanner {
    
    /*!
     * \brief gate or zero output when FM quieting not detected
     * \ingroup level_controllers_blk
     */
    class SCANNER_API noise_squelch_ff :
      public gr::analog::squelch_base_ff, virtual public block
    {
    protected:
      virtual void update_state(const float &in) = 0;
      virtual bool mute() const = 0;

    public:
      // scanner::noise_squelch_ff::sptr
      typedef boost::shared_ptr<noise_squelch_ff> sptr;
      
      /*!
       * \brief Make noise-based squelch block.
       *
       * \param db threshold (in dB) for noise squelch
       * \param alpha Gain of averaging filter
       * \param ramp sets response characteristic.
       * \param gate if true, no output if no squelch tone.
       *             if false, output 0's if no squelch tone.
       */
      static sptr make(double db, double alpha=0.0001,
		       int ramp=0, bool gate=false);

      virtual std::vector<float> squelch_range() const = 0;

      virtual double threshold() const = 0;
      virtual void set_threshold(double db) = 0;
      virtual void set_alpha(double alpha) = 0;

      virtual int ramp() const = 0;
      virtual void set_ramp(int ramp) = 0;
      virtual bool gate() const = 0;
      virtual void set_gate(bool gate) = 0;
      virtual bool unmuted() const = 0;
    };

  } /* namespace scanner */
} /* namespace gr */

#endif /* INCLUDED_SCANNER_NOISE_SQUELCH_FF_H */
